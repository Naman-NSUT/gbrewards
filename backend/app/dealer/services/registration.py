"""Warranty registration — the transaction the whole product is built around.

Everything here happens in ONE database transaction, or none of it does:

    resolve serial → upsert customer → create warranty → credit points
    → write the warranty event → queue the SMS

The points credit is in the same transaction as the warranty, so a crash between
them is impossible rather than merely unlikely. The SMS is queued as a row inside
the transaction but SENT outside it, because a slow provider must not hold a
database transaction open while a dealer waits, and an SMS failure must not roll
back a completed sale.

Abuse resistance is not a later hardening pass; it is the shape of this function:
  * a serial can carry only one live warranty                   (DB partial index)
  * a warranty can be paid for only once                        (DB partial index)
  * a retry returns the original result                         (idempotency)
  * the clock is server-derived                                 (warranty_dates)
  * velocity limits cap a compromised login                     (rate limiter)
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import DealerStaff
from app.dealer.models.unit import DealerUnit as ProductUnit
from app.dealer.models.warranty import Warranty, WarrantyEvent
from app.dealer.services import ledger
from app.dealer.services.unitsource import (
    UnitFacts,
    get_unit_source,
    normalise_serial,
)
from app.dealer.services.warranty_dates import decide_clock

logger = get_logger(__name__)


@dataclass
class RegistrationResult:
    warranty: Warranty
    points_awarded: int
    balance: int
    # True when this call replayed an existing registration rather than creating
    # one. The app shows "already registered" instead of a second success screen.
    idempotent: bool
    # Reserved: set when a registration was accepted without the unit being
    # fully verified. Always False today.
    unit_unverified: bool


def _resolve_unit_facts(session: Session, serial: str) -> UnitFacts:
    """Look up the unit. One database now, so an unknown serial is definitive.

    This used to tolerate a missing unit and register anyway, because the unit
    lived in another service that could be down mid-sale. On a shared database
    that reasoning is gone: if `product_units` has no row, the code on the label
    was never manufactured, which means a typo or a counterfeit. Refusing is now
    strictly better than proceeding.
    """
    facts = get_unit_source(session).get(serial)
    if facts is None:
        raise AppError(
            "invalid_serial",
            404,
            "No mattress found for this code. Check the number printed under the QR.",
        )
    if facts.source_status == "void":
        # A label is voided when a print run is scrapped or a sheet goes missing.
        # Letting a voided label be registered would turn "we lost 200 labels"
        # into 200 payable registrations.
        raise AppError(
            "unit_void",
            409,
            "This label has been cancelled. Contact GoodBed before selling this unit.",
        )
    return facts


def _upsert_customer(
    session: Session,
    *,
    phone: str,
    name: str,
    address: str | None,
    city: str | None,
    state: str | None,
    pincode: str | None,
) -> Customer:
    customer = session.execute(select(Customer).where(Customer.phone == phone)).scalar_one_or_none()
    if customer is None:
        customer = Customer(phone=phone, name=name)
        session.add(customer)
    # Only fill blanks. A repeat buyer's existing details must not be silently
    # overwritten by a shorter form at a different shop.
    customer.name = customer.name or name
    for field, value in (
        ("address", address),
        ("city", city),
        ("state", state),
        ("pincode", pincode),
    ):
        if value and not getattr(customer, field):
            setattr(customer, field, value)
    session.flush()
    return customer


def register(
    session: Session,
    *,
    staff: DealerStaff,
    raw_serial: str,
    customer_phone: str,
    customer_name: str,
    invoice_ref: str,
    invoice_date: date | None = None,
    customer_address: str | None = None,
    customer_city: str | None = None,
    customer_state: str | None = None,
    customer_pincode: str | None = None,
    now: datetime | None = None,
) -> RegistrationResult:
    """Register a warranty and credit the dealer. Caller commits."""
    serial = normalise_serial(raw_serial)
    if not serial:
        raise AppError("invalid_serial", 400, "No serial was scanned")

    dealer_id = staff.dealer_id

    # --- Is this serial already registered? ---------------------------------
    # Checked explicitly so a genuine duplicate returns a clear, friendly answer
    # rather than an IntegrityError from the partial unique index. The index is
    # still the real guarantee; this is just the good error message.
    existing = session.execute(
        select(Warranty).where(
            Warranty.serial == serial,
            Warranty.status.in_(
                ("pending_confirmation", "pending_review", "pending_backdate", "active", "claimed")
            ),
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.dealer_id == dealer_id:
            # This dealer's own earlier registration — replay it rather than
            # scolding someone who lost their network and tapped again.
            return RegistrationResult(
                warranty=existing,
                points_awarded=_credited_points(session, existing.id),
                balance=ledger.balance(session, dealer_id),
                idempotent=True,
                unit_unverified=existing.unit_unverified,
            )
        raise AppError(
            "already_registered",
            409,
            "This unit is already registered under another dealer",
            {"registered_on": existing.warranty_start_date.isoformat()},
        )

    # --- Open scanning -------------------------------------------------------
    # Any registered dealer may register any manufactured label. There is no
    # allocation gate; stock is not scoped to shops.
    #
    # What still bounds this, and what does not:
    #   * BOUNDED: one warranty per serial (uq_warranties_live_serial), so each
    #     label pays exactly once no matter who scans it. Total payout is capped
    #     by labels printed, not by dealer behaviour.
    #   * BOUNDED: void labels are unregistrable, so a scrapped print run cannot
    #     be turned into registrations.
    #   * BOUNDED: per-staff and per-dealer velocity limits in the router.
    #     These are now the main thing between a compromised login and a large
    #     payout, so they are worth tuning down if abuse appears.
    #   * NOT BOUNDED: attribution. Whoever scans first is paid. A label
    #     photographed in a warehouse or another shop registers just as well as
    #     one actually sold, and the shop that really sold it is then refused
    #     with `already_registered`.
    #
    # The remaining defences are therefore detective rather than preventive: the
    # audit trail, the customer confirmation reply, and the velocity limits.
    # See docs/dealer/DECISIONS.md.

    facts = _resolve_unit_facts(session, serial)
    warranty_months = facts.warranty_months or settings.default_warranty_months

    clock = decide_clock(warranty_months=warranty_months, invoice_date=invoice_date, now=now)

    customer = _upsert_customer(
        session,
        phone=customer_phone,
        name=customer_name,
        address=customer_address,
        city=customer_city,
        state=customer_state,
        pincode=customer_pincode,
    )

    unit_row = session.execute(
        select(ProductUnit).where(ProductUnit.token == serial)
    ).scalar_one_or_none()

    if clock.needs_approval:
        status = "pending_backdate"
    elif settings.require_customer_confirmation:
        status = "pending_confirmation"
    else:
        status = "active"

    warranty = Warranty(
        serial=serial,
        unit_id=unit_row.id if unit_row else None,
        product_id=facts.product_id,
        model_name=facts.model_name,
        model_code=facts.model_code,
        warranty_months=warranty_months,
        dealer_id=dealer_id,
        staff_id=staff.id,
        customer_id=customer.id,
        invoice_ref=invoice_ref,
        invoice_date=invoice_date,
        warranty_start_date=clock.start_date,
        warranty_end_date=clock.end_date,
        backdate_days=clock.backdate_days,
        status=status,
        source="dealer",
        registered_at=now or datetime.now(UTC),
        unit_unverified=False,
    )
    session.add(warranty)

    try:
        session.flush()
    except IntegrityError as exc:
        # Two devices submitted the same serial at the same instant and both got
        # past the SELECT above. The partial unique index is what actually stops
        # the double registration; this turns it into a clean 409.
        session.rollback()
        raise AppError(
            "already_registered", 409, "This unit was just registered by someone else"
        ) from exc

    points = 0
    # Per product: a premium mattress is worth more to register than an entry
    # model, exactly as worker scan points already vary by product.
    rate = ledger.current_rate(session, product_id=facts.product_id)
    # Points credit immediately UNLESS the warranty is waiting on a human — an
    # unapproved backdate or an unconfirmed customer must not pay out first and
    # ask questions later.
    if status == "active" and rate is not None and rate.points_per_registration > 0:
        points = rate.points_per_registration
        ledger.add_entry(
            session,
            dealer_id=dealer_id,
            staff_id=staff.id,
            amount=points,
            type=ledger.REGISTRATION_CREDIT,
            warranty_id=warranty.id,
            rate_version_id=rate.id,
            metadata={"serial": serial},
        )

    session.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event="registered",
            from_status=None,
            to_status=status,
            actor_type="dealer_staff",
            actor_id=staff.id,
            event_metadata={
                "serial": serial,
                "invoice_ref": invoice_ref,
                "backdate_days": clock.backdate_days,
                "points": points,
            },
        )
    )
    session.flush()

    return RegistrationResult(
        warranty=warranty,
        points_awarded=points,
        balance=ledger.balance(session, dealer_id),
        idempotent=False,
        unit_unverified=False,
    )


def _credited_points(session: Session, warranty_id: uuid.UUID) -> int:
    from app.dealer.models.ledger_entry import LedgerEntry

    entry = session.execute(
        select(LedgerEntry).where(
            LedgerEntry.warranty_id == warranty_id,
            LedgerEntry.type == ledger.REGISTRATION_CREDIT,
        )
    ).scalar_one_or_none()
    return entry.amount if entry else 0
