"""Warranty claims raised by customers, worked by the support desk.

Claims are created on the public site; this is where they are triaged. The one
piece of real logic here is what happens to the WARRANTY when a claim closes: a
warranty parked in 'claimed' while its claim was in review must not stay there
after the claim is rejected, or the customer can never raise another and the
serial reads as consumed forever.
"""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import (
    Pagination,
    count_of,
    day_window,
    like,
    pagination,
    to_warranty_item,
)
from app.dealer.models.claim import Claim
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer
from app.dealer.models.warranty import Warranty, WarrantyEvent
from app.dealer.schemas.admin import (
    ClaimDetailOut,
    ClaimListItem,
    ClaimUpdateIn,
    CustomerBrief,
    CustomerOut,
    DealerBrief,
    Paginated,
)
from app.dealer.services.audit import record_audit
from app.dealer.services.unitsource import normalise_serial
from app.models.admin import Admin

router = APIRouter(tags=["admin-claims"])

OPEN_STATUSES = ("open", "in_review")
TERMINAL_STATUSES = ("approved", "rejected", "closed")


def claim_select() -> Select[tuple[Claim, Warranty, Customer, Dealer]]:
    return (
        select(Claim, Warranty, Customer, Dealer)
        .join(Warranty, Warranty.id == Claim.warranty_id)
        .join(Customer, Customer.id == Claim.customer_id)
        .outerjoin(Dealer, Dealer.id == Warranty.dealer_id)
    )


def to_claim_item(
    claim: Claim, warranty: Warranty, customer: Customer, dealer: Dealer | None
) -> ClaimListItem:
    raised_on = claim.created_at.astimezone(UTC).date()
    return ClaimListItem(
        id=claim.id,
        reference=claim.reference,
        status=claim.status,
        issue_type=claim.issue_type,
        description=claim.description,
        warranty_id=warranty.id,
        serial=warranty.serial,
        model_name=warranty.model_name,
        customer=CustomerBrief(id=customer.id, name=customer.name, phone=customer.phone),
        dealer=(
            DealerBrief(
                id=dealer.id,
                code=dealer.code,
                name=dealer.name,
                status=dealer.status,
                city=dealer.city,
            )
            if dealer
            else None
        ),
        warranty_end_date=warranty.warranty_end_date,
        # Judged on the day the claim was RAISED, not today: a claim that came in
        # inside the window does not lapse because it sat in a queue.
        in_warranty=(
            warranty.warranty_start_date <= raised_on <= warranty.warranty_end_date
        ),
        handled_by_admin_id=claim.handled_by_admin_id,
        resolved_at=claim.resolved_at,
        created_at=claim.created_at,
    )


@router.get("/claims", response_model=Paginated[ClaimListItem])
def list_claims(
    status: str | None = Query(
        default=None, pattern="^(open|in_review|approved|rejected|closed)$"
    ),
    q: str | None = Query(
        default=None, max_length=200, description="reference, serial, mobile or name"
    ),
    dealer_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Paginated[ClaimListItem]:
    stmt = claim_select()
    if status:
        stmt = stmt.where(Claim.status == status)
    if dealer_id:
        stmt = stmt.where(Warranty.dealer_id == dealer_id)
    if q:
        term = like(q)
        stmt = stmt.where(
            or_(
                Claim.reference.ilike(term),
                Warranty.serial == normalise_serial(q),
                Warranty.serial.ilike(term),
                Customer.phone.ilike(f"%{q.strip().lstrip('+')}%"),
                Customer.name.ilike(term),
            )
        )

    start, end = day_window(date_from, date_to)
    if start is not None:
        stmt = stmt.where(Claim.created_at >= start)
    if end is not None:
        stmt = stmt.where(Claim.created_at < end)

    total = count_of(db, stmt)
    rows = db.execute(
        stmt.order_by(Claim.created_at.desc()).limit(page.limit).offset(page.offset)
    ).all()
    return Paginated[ClaimListItem](
        items=[to_claim_item(*row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/claims/{claim_id}", response_model=ClaimDetailOut)
def get_claim(
    claim_id: uuid.UUID,
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ClaimDetailOut:
    row = db.execute(claim_select().where(Claim.id == claim_id)).one_or_none()
    if row is None:
        raise AppError("claim_not_found", 404, "No such claim")
    claim, warranty, customer, dealer = row
    return ClaimDetailOut(
        claim=to_claim_item(claim, warranty, customer, dealer),
        resolution_note=claim.resolution_note,
        warranty=to_warranty_item(warranty, customer, dealer),
        customer=CustomerOut.model_validate(customer),
    )


@router.patch("/claims/{claim_id}", response_model=ClaimDetailOut)
def update_claim(
    claim_id: uuid.UUID,
    body: ClaimUpdateIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> ClaimDetailOut:
    """Move a claim along. Closing one requires a note.

    A rejected or closed claim releases the warranty back to 'active' when no
    other claim is still open on it: 'claimed' means "a claim is live against
    this warranty", and leaving it set after the claim ends would block the
    customer from ever raising another.
    """
    row = db.execute(claim_select().where(Claim.id == claim_id)).one_or_none()
    if row is None:
        raise AppError("claim_not_found", 404, "No such claim")
    claim, warranty, customer, dealer = row

    if body.status in TERMINAL_STATUSES and not (
        body.resolution_note and body.resolution_note.strip()
    ):
        raise AppError(
            "resolution_note_required",
            400,
            "Closing a claim requires a note explaining the outcome",
        )

    previous = claim.status
    claim.status = body.status
    if body.resolution_note:
        claim.resolution_note = body.resolution_note
    claim.handled_by_admin_id = admin.id
    if body.status in TERMINAL_STATUSES:
        claim.resolved_at = datetime.now(UTC)
    db.flush()

    if body.status in ("rejected", "closed") and warranty.status == "claimed":
        still_open = db.execute(
            select(Claim.id).where(
                Claim.warranty_id == warranty.id,
                Claim.id != claim.id,
                Claim.status.in_(OPEN_STATUSES),
            )
        ).first()
        if still_open is None:
            warranty.status = "active"
            db.add(
                WarrantyEvent(
                    warranty_id=warranty.id,
                    event="claim_closed",
                    from_status="claimed",
                    to_status="active",
                    actor_type="admin",
                    actor_id=admin.id,
                    reason=body.resolution_note,
                    event_metadata={"claim_reference": claim.reference, "outcome": body.status},
                )
            )

    record_audit(
        db,
        action="update_claim",
        entity_type="claim",
        entity_id=claim.id,
        actor_id=admin.id,
        reason=body.resolution_note,
        ip=client_ip(request),
        metadata={
            "reference": claim.reference,
            "from": previous,
            "to": claim.status,
            "warranty_id": str(warranty.id),
        },
    )
    db.commit()

    return ClaimDetailOut(
        claim=to_claim_item(claim, warranty, customer, dealer),
        resolution_note=claim.resolution_note,
        warranty=to_warranty_item(warranty, customer, dealer),
        customer=CustomerOut.model_validate(customer),
    )
