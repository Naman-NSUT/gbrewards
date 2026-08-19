"""Warranty search, detail, void and customer correction.

THE SALE RECORD IS THE PRODUCT, so this is the screen where its integrity is
maintained. Two rules shape every endpoint here:

  * Nothing is edited destructively. A void writes a compensating ledger debit
    and a warranty event; a customer correction writes an audited event with the
    previous values in it. The history is always reconstructable.
  * Expiry is derived, never stored, so the reported status is computed at read
    time by warranty.display_status — see _common.to_warranty_item.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_current_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import (
    Pagination,
    allocation_select,
    count_of,
    day_window,
    like,
    pagination,
    to_allocation_out,
    to_warranty_item,
    warranty_select,
)
from app.dealer.models.allocation import Allocation
from app.dealer.models.claim import Claim
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.warranty import Warranty, WarrantyEvent
from app.dealer.schemas.admin import (
    ClaimBrief,
    CustomerOut,
    DealerBrief,
    EditCustomerIn,
    LedgerEntryOut,
    Paginated,
    StaffBrief,
    VoidWarrantyIn,
    WarrantyDetailOut,
    WarrantyEventOut,
    WarrantyListItem,
)
from app.dealer.services import sms
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.audit import record_audit
from app.dealer.services.unitsource import normalise_serial
from app.dealer.services.warranty_dates import business_today
from app.models.admin import Admin

router = APIRouter(tags=["admin-warranties"])


def _get_warranty(db: Session, warranty_id: uuid.UUID) -> Warranty:
    warranty = db.get(Warranty, warranty_id)
    if warranty is None:
        raise AppError("warranty_not_found", 404, "No such warranty")
    return warranty


def _event_out(event: WarrantyEvent, actor_names: dict[uuid.UUID, str]) -> WarrantyEventOut:
    return WarrantyEventOut(
        id=event.id,
        warranty_id=event.warranty_id,
        event=event.event,
        from_status=event.from_status,
        to_status=event.to_status,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        actor_name=actor_names.get(event.actor_id) if event.actor_id else None,
        reason=event.reason,
        metadata=event.event_metadata,
        created_at=event.created_at,
    )


def resolve_actor_names(db: Session, actor_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Name the humans behind a timeline.

    Actor ids are polymorphic (admin, dealer staff or customer) and deliberately
    not foreign keys — an event must survive the actor's row being changed. Two
    lookups here beat a UUID nobody can read on the support screen.
    """
    if not actor_ids:
        return {}
    names: dict[uuid.UUID, str] = {}
    for admin_row in db.execute(
        select(Admin.id, Admin.name).where(Admin.id.in_(actor_ids))
    ):
        names[admin_row[0]] = admin_row[1]
    for staff_row in db.execute(
        select(DealerStaff.id, DealerStaff.name).where(DealerStaff.id.in_(actor_ids))
    ):
        names[staff_row[0]] = staff_row[1]
    for row in db.execute(
        select(Customer.id, Customer.name).where(Customer.id.in_(actor_ids))
    ):
        names.setdefault(row[0], row[1])
    return names


@router.get("/warranties", response_model=Paginated[WarrantyListItem])
def list_warranties(
    q: str | None = Query(default=None, max_length=200, description="serial, mobile or invoice"),
    dealer_id: uuid.UUID | None = None,
    dealer_code: str | None = Query(default=None, max_length=32),
    status: str | None = Query(
        default=None,
        pattern="^(pending_confirmation|pending_review|pending_backdate|active|claimed"
        "|voided|expired)$",
    ),
    source: str | None = Query(default=None, pattern="^(dealer|customer_self|admin|migration)$"),
    backdated: bool | None = None,
    unverified: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Paginated[WarrantyListItem]:
    stmt = warranty_select()

    if q:
        term = like(q)
        serial = normalise_serial(q)
        stmt = stmt.where(
            or_(
                Warranty.serial == serial,
                Warranty.serial.ilike(term),
                Warranty.invoice_ref.ilike(term),
                Customer.phone.ilike(f"%{q.strip().lstrip('+')}%"),
                Customer.name.ilike(term),
            )
        )
    if dealer_id:
        stmt = stmt.where(Warranty.dealer_id == dealer_id)
    if dealer_code:
        stmt = stmt.where(Dealer.code.ilike(like(dealer_code)))
    if status == "expired":
        # 'expired' is not a stored status. Filtering on it means the same thing
        # the display does: active, but the end date has passed.
        stmt = stmt.where(
            Warranty.status == "active", Warranty.warranty_end_date < business_today()
        )
    elif status == "active":
        stmt = stmt.where(
            Warranty.status == "active", Warranty.warranty_end_date >= business_today()
        )
    elif status:
        stmt = stmt.where(Warranty.status == status)
    if source:
        stmt = stmt.where(Warranty.source == source)
    if backdated is not None:
        stmt = stmt.where(Warranty.backdate_days > 0 if backdated else Warranty.backdate_days == 0)
    if unverified is not None:
        stmt = stmt.where(Warranty.unit_unverified.is_(unverified))

    start, end = day_window(date_from, date_to)
    if start is not None:
        stmt = stmt.where(Warranty.registered_at >= start)
    if end is not None:
        stmt = stmt.where(Warranty.registered_at < end)

    total = count_of(db, stmt)
    rows = db.execute(
        stmt.order_by(Warranty.registered_at.desc()).limit(page.limit).offset(page.offset)
    ).all()
    return Paginated[WarrantyListItem](
        items=[to_warranty_item(w, c, d) for w, c, d in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/warranties/{warranty_id}", response_model=WarrantyDetailOut)
def get_warranty(
    warranty_id: uuid.UUID,
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> WarrantyDetailOut:
    row = db.execute(warranty_select().where(Warranty.id == warranty_id)).one_or_none()
    if row is None:
        raise AppError("warranty_not_found", 404, "No such warranty")
    return build_warranty_detail(db, row[0], row[1], row[2])


def build_warranty_detail(
    db: Session, warranty: Warranty, customer: Customer, dealer: Dealer | None
) -> WarrantyDetailOut:
    """The full record: who sold it, what happened to it, what it paid."""
    staff = db.get(DealerStaff, warranty.staff_id) if warranty.staff_id else None

    events = list(
        db.execute(
            select(WarrantyEvent)
            .where(WarrantyEvent.warranty_id == warranty.id)
            .order_by(WarrantyEvent.created_at.desc())
        ).scalars()
    )
    actor_names = resolve_actor_names(db, {e.actor_id for e in events if e.actor_id})

    entries = list(
        db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.warranty_id == warranty.id)
            .order_by(LedgerEntry.created_at.asc())
        ).scalars()
    )
    claims = list(
        db.execute(
            select(Claim)
            .where(Claim.warranty_id == warranty.id)
            .order_by(Claim.created_at.desc())
        ).scalars()
    )
    allocation_row = db.execute(
        allocation_select()
        .where(Allocation.serial == warranty.serial)
        .order_by(Allocation.allocated_at.desc())
        .limit(1)
    ).one_or_none()

    return WarrantyDetailOut(
        warranty=to_warranty_item(warranty, customer, dealer),
        is_expired=warranty_svc.is_expired(warranty),
        customer=CustomerOut.model_validate(customer),
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
        staff=(
            StaffBrief(id=staff.id, name=staff.name, phone=staff.phone, role=staff.role)
            if staff
            else None
        ),
        allocation=to_allocation_out(allocation_row) if allocation_row is not None else None,
        events=[_event_out(e, actor_names) for e in events],
        ledger_entries=[
            LedgerEntryOut(
                id=e.id,
                dealer_id=e.dealer_id,
                amount=e.amount,
                type=e.type,
                warranty_id=e.warranty_id,
                redemption_id=e.redemption_id,
                rate_version_id=e.rate_version_id,
                admin_id=e.admin_id,
                staff_id=e.staff_id,
                reason=e.reason,
                metadata=e.entry_metadata,
                created_at=e.created_at,
            )
            for e in entries
        ],
        claims=[
            ClaimBrief(
                id=c.id,
                reference=c.reference,
                status=c.status,
                issue_type=c.issue_type,
                created_at=c.created_at,
            )
            for c in claims
        ],
        void_reason=warranty.void_reason,
        voided_at=warranty.voided_at,
        proof_file_key=warranty.proof_file_key,
    )


@router.post("/warranties/{warranty_id}/void", response_model=WarrantyDetailOut)
def void_warranty(
    warranty_id: uuid.UUID,
    body: VoidWarrantyIn,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> WarrantyDetailOut:
    """Void a warranty, by default reversing the points it paid.

    Clawback is a parameter and not a policy because the two reasons for voiding
    are different: a fake or duplicated registration must give the points back,
    while correcting a genuine sale recorded against the wrong serial should not
    punish the dealer twice.
    """
    warranty = _get_warranty(db, warranty_id)
    if warranty.status == "voided":
        raise AppError("already_voided", 409, "This warranty is already voided")

    warranty_svc.void(
        db,
        warranty=warranty,
        reason=body.reason,
        actor_type="admin",
        actor_id=admin.id,
        clawback=body.clawback,
    )

    message_id = None
    if body.notify_customer:
        # Opt-in: an admin voiding to fix a typo should not tell the customer
        # their warranty was cancelled, but a genuine cancellation should.
        message = sms.queue(
            db,
            phone=warranty.customer.phone,
            template_key="warranty_voided",
            variables={
                "name": warranty.customer.name,
                "serial": warranty.serial[:12],
                "link": f"{settings.public_base_url}/w/{warranty.id}",
            },
            warranty_id=warranty.id,
        )
        message_id = message.id

    # No audit row is written here: warranty.void already wrote one (action
    # 'void_warranty', reason enforced) and its warranty event records how many
    # points were reversed. A second row for one action would make the audit
    # feed overstate how often warranties are voided.
    db.commit()

    if message_id is not None:
        # After commit, on purpose: a slow provider must not hold the
        # transaction, and a failed SMS must not undo the void.
        sms.flush(db, message_id)

    row = db.execute(warranty_select().where(Warranty.id == warranty_id)).one()
    return build_warranty_detail(db, row[0], row[1], row[2])


@router.patch("/warranties/{warranty_id}/customer", response_model=WarrantyDetailOut)
def edit_customer(
    warranty_id: uuid.UUID,
    body: EditCustomerIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> WarrantyDetailOut:
    """Correct the buyer's details on a warranty. Reason required, always.

    A changed PHONE repoints the warranty at the customer who owns that number
    (creating them if new) rather than rewriting the existing customer's number,
    because the old number probably belongs to a real other person whose own
    warranties must not follow the edit.
    """
    warranty = _get_warranty(db, warranty_id)
    customer = db.get(Customer, warranty.customer_id)
    if customer is None:  # pragma: no cover - customer_id is NOT NULL with an FK
        raise AppError("customer_not_found", 404, "This warranty has no customer")

    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    if not changes:
        raise AppError("nothing_to_update", 400, "No fields supplied")

    before = {
        "customer_id": str(customer.id),
        "name": customer.name,
        "phone": customer.phone,
    }
    new_phone = changes.pop("phone", None)
    target = customer

    if new_phone and new_phone != customer.phone:
        owner = db.execute(
            select(Customer).where(Customer.phone == new_phone)
        ).scalar_one_or_none()
        if owner is None:
            owner = Customer(phone=new_phone, name=changes.get("name") or customer.name)
            db.add(owner)
            db.flush()
        target = owner
        warranty.customer_id = target.id

    for field, value in changes.items():
        if value is not None:
            setattr(target, field, value)
    db.flush()

    after = {"customer_id": str(target.id), "name": target.name, "phone": target.phone}
    db.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event="customer_edited",
            from_status=warranty.status,
            to_status=warranty.status,
            actor_type="admin",
            actor_id=admin.id,
            reason=body.reason,
            event_metadata={"before": before, "after": after},
        )
    )
    record_audit(
        db,
        action="edit_customer",
        entity_type="warranty",
        entity_id=warranty.id,
        actor_id=admin.id,
        reason=body.reason,
        ip=client_ip(request),
        metadata={"before": before, "after": after},
    )
    db.commit()

    row = db.execute(warranty_select().where(Warranty.id == warranty_id)).one()
    return build_warranty_detail(db, row[0], row[1], row[2])
