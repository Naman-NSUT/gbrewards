"""Warranty lifecycle transitions after registration.

Every transition here does the same three things in one transaction: move the
status, write a WarrantyEvent, and — where points are involved — write a
COMPENSATING ledger entry. Nothing edits or deletes history.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.allocation import Allocation
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.warranty import Warranty, WarrantyEvent
from app.dealer.services import ledger
from app.dealer.services.audit import record_audit
from app.dealer.services.warranty_dates import business_today


def _event(
    session: Session,
    warranty: Warranty,
    *,
    event: str,
    from_status: str,
    to_status: str,
    actor_type: str,
    actor_id: uuid.UUID | None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event=event,
            from_status=from_status,
            to_status=to_status,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            event_metadata=metadata,
        )
    )


def is_expired(warranty: Warranty, today: date | None = None) -> bool:
    """Expiry is derived, never stored — see models/warranty.py."""
    ref = today or business_today()
    return warranty.warranty_end_date < ref


def display_status(warranty: Warranty) -> str:
    """What a human should be told. Folds derived expiry into the stored status."""
    if warranty.status == "active" and is_expired(warranty):
        return "expired"
    return warranty.status


def void(
    session: Session,
    *,
    warranty: Warranty,
    reason: str,
    actor_type: str = "admin",
    actor_id: uuid.UUID | None = None,
    clawback: bool = True,
    free_serial: bool = True,
) -> int:
    """Void a warranty, optionally reversing the points it paid.

    Returns the number of points clawed back.

    The clawback is a compensating DEBIT, never an edit of the original credit,
    so "this dealer earned 50 then had it reversed" stays visible instead of
    becoming "this dealer never earned anything".

    Balance is allowed to go negative. The alternative — refusing to claw back
    from a dealer who has already spent the points — makes registering fake sales
    and redeeming quickly a profitable strategy. A negative balance is a debt the
    client can see and chase; a skipped clawback is a loss they cannot.
    """
    if not (reason and reason.strip()):
        raise AppError("reason_required", 400, "Voiding a warranty requires a reason")
    if warranty.status == "voided":
        return 0

    previous = warranty.status
    clawed = 0

    if clawback:
        credit = session.execute(
            select(LedgerEntry).where(
                LedgerEntry.warranty_id == warranty.id,
                LedgerEntry.type == ledger.REGISTRATION_CREDIT,
            )
        ).scalar_one_or_none()
        already_reversed = session.execute(
            select(LedgerEntry).where(
                LedgerEntry.warranty_id == warranty.id,
                LedgerEntry.type == ledger.REGISTRATION_REVERSAL,
            )
        ).scalar_one_or_none()
        if credit is not None and already_reversed is None and warranty.dealer_id:
            clawed = credit.amount
            ledger.add_entry(
                session,
                dealer_id=warranty.dealer_id,
                staff_id=warranty.staff_id,
                amount=-clawed,
                type=ledger.REGISTRATION_REVERSAL,
                warranty_id=warranty.id,
                rate_version_id=credit.rate_version_id,
                admin_id=actor_id if actor_type == "admin" else None,
                reason=reason,
            )

    warranty.status = "voided"
    warranty.voided_at = datetime.now(UTC)
    warranty.void_reason = reason

    if free_serial:
        # Release the allocation so a returned mattress can legitimately be sold
        # again. The partial unique index already permits a new warranty once
        # this one is voided; this keeps the allocation side consistent.
        allocation = session.execute(
            select(Allocation).where(
                Allocation.serial == warranty.serial,
                Allocation.status == "registered",
            )
        ).scalar_one_or_none()
        if allocation is not None:
            allocation.status = "allocated"

    _event(
        session,
        warranty,
        event="voided",
        from_status=previous,
        to_status="voided",
        actor_type=actor_type,
        actor_id=actor_id,
        reason=reason,
        metadata={"points_reversed": clawed},
    )
    record_audit(
        session,
        action="void_warranty",
        entity_type="warranty",
        entity_id=warranty.id,
        actor_type=actor_type,
        actor_id=actor_id,
        reason=reason,
        metadata={"serial": warranty.serial, "points_reversed": clawed},
    )
    session.flush()
    return clawed


def confirm(
    session: Session,
    *,
    warranty: Warranty,
    actor_type: str = "customer",
) -> int:
    """The customer says "yes, I bought this".

    This records the acknowledgment ALWAYS, not only when it changes a status.

    With REQUIRE_CUSTOMER_CONFIRMATION off (the default), the SMS link lands on a
    warranty that is already active, so there is no transition to make. It would
    be easy to treat that as a no-op — and wrong. The customer's reply is the only
    thing that turns a dealer's CLAIM of a sale into EVIDENCE of one: it proves a
    real person at that number really bought that mattress. Discarding it would
    throw away the single most valuable signal this system can collect, on the
    majority path.

    Returns points credited, which is zero unless the warranty was actually
    waiting on this confirmation.
    """
    if warranty.status not in ("pending_confirmation", "active"):
        # Voided, claimed or awaiting review — confirmation is meaningless.
        return 0

    already_acknowledged = warranty.confirmed_at is not None
    previous = warranty.status
    points = 0

    if warranty.status == "pending_confirmation":
        warranty.status = "active"
        points = _credit_on_activation(session, warranty)

    warranty.confirmed_at = warranty.confirmed_at or datetime.now(UTC)
    warranty.customer.is_phone_verified = True

    if not already_acknowledged:
        _event(
            session,
            warranty,
            event="confirmed",
            from_status=previous,
            to_status=warranty.status,
            actor_type=actor_type,
            actor_id=warranty.customer_id,
            metadata={"points": points, "activated": previous == "pending_confirmation"},
        )
    session.flush()
    return points


def dispute(
    session: Session,
    *,
    warranty: Warranty,
    reason: str | None = None,
    actor_type: str = "customer",
) -> None:
    """The customer says they did not buy this.

    Deliberately does NOT void. Anyone holding the SMS link could otherwise
    destroy a genuine sale and the dealer's points with one tap. It raises a flag
    for a human instead — which is the right trade, because a false dispute
    costs an admin a phone call while a false void costs a real customer their
    five-year warranty.
    """
    _event(
        session,
        warranty,
        event="disputed",
        from_status=warranty.status,
        to_status=warranty.status,
        actor_type=actor_type,
        actor_id=warranty.customer_id,
        reason=reason,
        metadata={"serial": warranty.serial},
    )
    record_audit(
        session,
        action="dispute_warranty",
        entity_type="warranty",
        entity_id=warranty.id,
        actor_type=actor_type,
        actor_id=warranty.customer_id,
        reason=reason or "Customer disputed this registration",
        metadata={"serial": warranty.serial, "dealer_id": str(warranty.dealer_id)},
    )
    session.flush()


def approve(
    session: Session,
    *,
    warranty: Warranty,
    admin_id: uuid.UUID,
    reason: str,
    honour_requested_date: bool = True,
) -> int:
    """Approve a pending backdate or a customer self-registration."""
    if warranty.status not in ("pending_backdate", "pending_review"):
        raise AppError("not_pending", 409, "This warranty is not awaiting approval")
    previous = warranty.status

    if not honour_requested_date:
        # Approver accepted the sale but rejected the claimed date: reset the
        # clock to today rather than voiding a genuine registration.
        # This applies to customer self-registrations too — a customer stating
        # "I bought it 14 months ago" with a blurry invoice is exactly the case
        # an approver most often wants to accept on today's clock.
        from app.dealer.services.warranty_dates import add_months

        warranty.warranty_start_date = business_today()
        warranty.warranty_end_date = add_months(
            warranty.warranty_start_date, warranty.warranty_months
        )
        warranty.backdate_days = 0

    if previous == "pending_backdate":
        warranty.backdate_approved_by_admin_id = admin_id

    warranty.status = "active"
    points = _credit_on_activation(session, warranty)

    _event(
        session,
        warranty,
        event="approved",
        from_status=previous,
        to_status="active",
        actor_type="admin",
        actor_id=admin_id,
        reason=reason,
        metadata={"points": points, "honoured_requested_date": honour_requested_date},
    )
    record_audit(
        session,
        action=(
            "approve_backdate"
            if previous == "pending_backdate"
            else "approve_self_registration"
        ),
        entity_type="warranty",
        entity_id=warranty.id,
        actor_id=admin_id,
        reason=reason,
        metadata={"backdate_days": warranty.backdate_days},
    )
    session.flush()
    return points


def _credit_on_activation(session: Session, warranty: Warranty) -> int:
    """Pay for a warranty that is becoming active, exactly once.

    A customer self-registration pays nobody: the dealer did not do the work, and
    paying for it would reward the very non-compliance this system exists to
    surface.
    """
    if warranty.dealer_id is None or warranty.source != "dealer":
        return 0
    already = session.execute(
        select(LedgerEntry).where(
            LedgerEntry.warranty_id == warranty.id,
            LedgerEntry.type == ledger.REGISTRATION_CREDIT,
        )
    ).scalar_one_or_none()
    if already is not None:
        return already.amount

    if warranty.product_id is None:
        # Pre-merge or admin-created records without a product cannot be priced.
        return 0
    rate = ledger.current_rate(session, product_id=warranty.product_id)
    if rate is None or rate.points_per_registration <= 0:
        return 0
    ledger.add_entry(
        session,
        dealer_id=warranty.dealer_id,
        staff_id=warranty.staff_id,
        amount=rate.points_per_registration,
        type=ledger.REGISTRATION_CREDIT,
        warranty_id=warranty.id,
        rate_version_id=rate.id,
        metadata={"serial": warranty.serial},
    )
    return rate.points_per_registration
