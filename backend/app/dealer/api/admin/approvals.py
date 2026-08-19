"""The approval queue: backdate requests and customer self-registrations.

Two very different things share one queue because they need the same decision
from the same person, and because together they ARE the non-compliance report:

  pending_backdate  a dealer registered a sale older than the grace window. The
                    clock they asked for is recorded, honoured only on approval.
  pending_review    the CUSTOMER registered the unit because the dealer never
                    did. Nobody is paid for these — the dealer did not do the
                    work — but the selling dealer is named anyway, inferred from
                    who holds the allocation, because that name is the point.

Rejecting voids with NO clawback: a warranty that never reached 'active' was
never credited, so a reversal would debit points that were never paid.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
from app.core.deps import get_current_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, count_of, pagination
from app.dealer.api.admin.warranties import build_warranty_detail
from app.dealer.models.allocation import Allocation
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.warranty import Warranty
from app.dealer.schemas.admin import (
    ApprovalItem,
    ApproveIn,
    CustomerBrief,
    DealerBrief,
    Paginated,
    ReasonIn,
    StaffBrief,
    WarrantyDetailOut,
)
from app.dealer.services import sms
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.audit import record_audit
from app.dealer.services.warranty_dates import business_today
from app.models.admin import Admin

router = APIRouter(tags=["admin-approvals"])

PENDING = ("pending_backdate", "pending_review")


def _queue_select() -> Select[tuple[Warranty, Customer, Dealer, Dealer, DealerStaff]]:
    """The queue with its evidence, in one query.

    The second dealer join is the interesting one: a self-registration carries
    no dealer_id, so the seller is inferred from the allocation on that serial.
    LATERAL-free because a serial has at most one open allocation (enforced by
    uq_allocations_open_serial), so this cannot multiply rows.
    """
    holder = aliased(Dealer)
    return (
        select(Warranty, Customer, Dealer, holder, DealerStaff)
        .join(Customer, Customer.id == Warranty.customer_id)
        .outerjoin(Dealer, Dealer.id == Warranty.dealer_id)
        .outerjoin(
            Allocation,
            and_(
                Allocation.serial == Warranty.serial,
                Allocation.status.in_(("allocated", "registered")),
            ),
        )
        .outerjoin(holder, holder.id == Allocation.dealer_id)
        .outerjoin(DealerStaff, DealerStaff.id == Warranty.staff_id)
        .where(Warranty.status.in_(PENDING))
    )


def _to_item(
    warranty: Warranty,
    customer: Customer,
    dealer: Dealer | None,
    holder: Dealer | None,
    staff: DealerStaff | None,
) -> ApprovalItem:
    seller = dealer or holder
    registered_at = warranty.registered_at
    if registered_at.tzinfo is None:  # pragma: no cover - column is timestamptz
        registered_at = registered_at.replace(tzinfo=UTC)
    return ApprovalItem(
        id=warranty.id,
        serial=warranty.serial,
        model_name=warranty.model_name,
        status=warranty.status,
        source=warranty.source,
        warranty_months=warranty.warranty_months,
        warranty_start_date=warranty.warranty_start_date,
        warranty_end_date=warranty.warranty_end_date,
        invoice_ref=warranty.invoice_ref,
        requested_invoice_date=warranty.invoice_date,
        # What was actually claimed. backdate_days is stored at registration and
        # is the number the approver is really being asked about.
        days_back=warranty.backdate_days,
        registered_at=warranty.registered_at,
        waiting_days=(datetime.now(UTC) - registered_at).days,
        unit_unverified=warranty.unit_unverified,
        proof_file_key=warranty.proof_file_key,
        customer=CustomerBrief(id=customer.id, name=customer.name, phone=customer.phone),
        dealer=(
            DealerBrief(
                id=seller.id,
                code=seller.code,
                name=seller.name,
                status=seller.status,
                city=seller.city,
            )
            if seller
            else None
        ),
        dealer_source=("warranty" if dealer else "allocation" if holder else None),
        staff=(
            StaffBrief(id=staff.id, name=staff.name, phone=staff.phone, role=staff.role)
            if staff
            else None
        ),
    )


@router.get("/approvals", response_model=Paginated[ApprovalItem])
def list_approvals(
    status: str | None = Query(default=None, pattern="^(pending_backdate|pending_review)$"),
    dealer_id: uuid.UUID | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Paginated[ApprovalItem]:
    stmt = _queue_select()
    if status:
        stmt = stmt.where(Warranty.status == status)
    if dealer_id:
        # Matches either the registering dealer or the dealer who held the
        # allocation, so filtering by a dealer also shows the sales they DIDN'T
        # record — which is the whole reason this queue exists.
        stmt = stmt.where(
            or_(Warranty.dealer_id == dealer_id, Allocation.dealer_id == dealer_id)
        )

    total = count_of(db, stmt)
    rows = db.execute(
        # Oldest first: this is a work queue, and the thing that has been waiting
        # longest is the thing a customer is most likely already chasing.
        stmt.order_by(Warranty.registered_at.asc()).limit(page.limit).offset(page.offset)
    ).all()
    return Paginated[ApprovalItem](
        items=[_to_item(*row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/approvals/count")
def pending_count(
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Badge counts for the nav. One grouped count, called on every page load."""
    counts = dict.fromkeys(PENDING, 0)
    rows = db.execute(
        select(Warranty.status, func.count(Warranty.id))
        .where(Warranty.status.in_(PENDING))
        .group_by(Warranty.status)
    ).all()
    for status, count in rows:
        counts[status] = int(count)
    counts["total"] = sum(counts[status] for status in PENDING)
    return counts


def _get_pending(db: Session, warranty_id: uuid.UUID) -> Warranty:
    warranty = db.get(Warranty, warranty_id)
    if warranty is None:
        raise AppError("warranty_not_found", 404, "No such warranty")
    if warranty.status not in PENDING:
        raise AppError(
            "not_pending",
            409,
            "This warranty is not awaiting approval",
            {"status": warranty.status},
        )
    return warranty


@router.post("/approvals/{warranty_id}/approve", response_model=WarrantyDetailOut)
def approve(
    warranty_id: uuid.UUID,
    body: ApproveIn,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> WarrantyDetailOut:
    """Accept the registration. Pays the dealer only if the dealer registered it.

    warranty.approve owns the money and the state change (including refusing to
    pay a customer self-registration — see _credit_on_activation). This endpoint
    owns the transaction and the customer SMS, which is the first message the
    buyer gets for a warranty that has been sitting in a queue.
    """
    warranty = _get_pending(db, warranty_id)
    warranty_svc.approve(
        db,
        warranty=warranty,
        admin_id=admin.id,
        reason=body.reason,
        honour_requested_date=body.honour_requested_date,
    )

    message = sms.queue(
        db,
        phone=warranty.customer.phone,
        template_key="warranty_registered",
        variables={
            "name": warranty.customer.name,
            "model": warranty.model_name or "your GoodBed mattress",
            "end_date": warranty.warranty_end_date.strftime("%d-%m-%Y"),
            "serial": warranty.serial[:12],
            "link": f"{settings.public_base_url}/w/{warranty.id}",
        },
        warranty_id=warranty.id,
    )
    db.commit()
    sms.flush(db, message.id)

    dealer = db.get(Dealer, warranty.dealer_id) if warranty.dealer_id else None
    return build_warranty_detail(db, warranty, warranty.customer, dealer)


@router.post("/approvals/{warranty_id}/reject", response_model=WarrantyDetailOut)
def reject(
    warranty_id: uuid.UUID,
    body: ReasonIn,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> WarrantyDetailOut:
    """Refuse the registration: void it, claw back nothing.

    Nothing was ever credited — points are withheld until a pending warranty
    becomes active — so a clawback would debit points that were never paid.
    Voiding also releases the allocation, so the dealer can register the sale
    properly with a truthful date.
    """
    warranty = _get_pending(db, warranty_id)
    previous = warranty.status

    warranty_svc.void(
        db,
        warranty=warranty,
        reason=body.reason,
        actor_type="admin",
        actor_id=admin.id,
        clawback=False,
    )
    record_audit(
        db,
        action=(
            "reject_backdate" if previous == "pending_backdate" else "reject_self_registration"
        ),
        entity_type="warranty",
        entity_id=warranty.id,
        actor_id=admin.id,
        reason=body.reason,
        metadata={
            "serial": warranty.serial,
            "backdate_days": warranty.backdate_days,
            "requested_invoice_date": (
                warranty.invoice_date.isoformat() if warranty.invoice_date else None
            ),
            "today": business_today().isoformat(),
        },
    )
    db.commit()

    dealer = db.get(Dealer, warranty.dealer_id) if warranty.dealer_id else None
    return build_warranty_detail(db, warranty, warranty.customer, dealer)
