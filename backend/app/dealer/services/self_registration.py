"""Customer self-registration — the flow that turns a missed sale into evidence.

A customer whose dealer never registered the warranty registers it themselves:
serial, their details, the invoice date, and a photo of the invoice. This is the
commercially most valuable path in the system, and not because of the warranty it
creates. Every row it produces names a dealer who was allocated a unit, sold it,
and did not register it. The approval queue this feeds IS the non-compliance
report — one row per proven miss, with the customer's invoice attached as proof.

Three decisions carry that value, and each one is a decision not to do the
obvious thing:

1. IT PAYS NOBODY. The dealer did not do the work. Paying them for a sale the
   customer had to record themselves would reward the exact behaviour this queue
   exists to surface, and would make "let the customer do it" a viable dealer
   strategy. `warranty_svc._credit_on_activation` already refuses to pay a
   non-dealer source, so this holds even after an admin approves the record.

2. IT ALWAYS WAITS FOR A HUMAN (`pending_review`). Everything here is a claim by
   an anonymous person on the internet: the serial, the date, the invoice. The
   clock they ask for is recorded exactly as stated, and an admin decides. A
   self-registration that activated itself would let anyone start a five-year
   warranty on any serial they can photograph.

3. IT RECORDS THE ALLOCATED DEALER even though that dealer did nothing. Without
   that link the queue is a pile of anonymous complaints; with it, it is a
   report the client can act on dealer by dealer.

The allocation is deliberately LEFT OPEN. A dealer's compliance number is
"allocated N, registered M", and this sale was not registered by the dealer —
flipping the allocation to 'registered' here would quietly repair the very
statistic the queue exists to expose. Nothing is lost by leaving it: the live
warranty on the serial already prevents a second registration, and a dealer who
scans it later gets "already registered" with zero points.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.dealer.models.allocation import Allocation
from app.dealer.models.dealer import Dealer
from app.dealer.models.product import DealerProduct as Product
from app.dealer.models.unit import DealerUnit as Unit
from app.dealer.models.warranty import LIVE_STATUSES, Warranty, WarrantyEvent
from app.dealer.services.registration import _upsert_customer
from app.dealer.services.unitsource import normalise_serial
from app.dealer.services.warranty_dates import decide_clock


@dataclass
class SelfRegistration:
    warranty: Warranty
    # The dealer the serial was allocated to, when there is one. This is the
    # dealer that failed to register, not one that did anything here.
    dealer: Dealer | None


def _unit_warranty_months(session: Session, unit: Unit | None) -> int:
    """Warranty length for a unit, from its product, with a safe default."""
    if unit is None:
        return settings.default_warranty_months
    product = session.get(Product, unit.product_id)
    return (product.warranty_months if product else None) or settings.default_warranty_months


def _unit_model_name(session: Session, unit: Unit | None) -> str | None:
    """Product name for a unit. Lives on products, not on the unit row."""
    if unit is None:
        return None
    product = session.get(Product, unit.product_id)
    return product.name if product else None


def normalise(raw_serial: str) -> str:
    serial = normalise_serial(raw_serial)
    if not serial:
        raise AppError("invalid_serial", 400, "Enter the serial number printed on the label")
    return serial


def live_warranty(session: Session, serial: str) -> Warranty | None:
    """The warranty currently occupying this serial, if any."""
    return session.execute(
        select(Warranty).where(Warranty.serial == serial, Warranty.status.in_(LIVE_STATUSES))
    ).scalar_one_or_none()


def selling_dealer(session: Session, warranty: Warranty) -> Dealer | None:
    return session.get(Dealer, warranty.dealer_id) if warranty.dealer_id else None


def allocated_dealer(session: Session, serial: str) -> Dealer | None:
    allocation = session.execute(
        select(Allocation).where(
            Allocation.serial == serial,
            Allocation.status.in_(("allocated", "registered")),
        )
    ).scalar_one_or_none()
    if allocation is None:
        return None
    return session.get(Dealer, allocation.dealer_id)


def submit(
    session: Session,
    *,
    raw_serial: str,
    customer_phone: str,
    customer_name: str,
    purchase_date: date,
    proof_key: str | None = None,
    invoice_ref: str | None = None,
    dealer_hint: str | None = None,
    customer_address: str | None = None,
    customer_city: str | None = None,
    customer_state: str | None = None,
    customer_pincode: str | None = None,
    ip: str | None = None,
) -> SelfRegistration:
    """Create a `pending_review` warranty from a customer's own submission.

    Caller owns the transaction.
    """
    serial = normalise(raw_serial)

    existing = live_warranty(session, serial)
    if existing is not None:
        # The router answers this case with the redacted record instead; reaching
        # it here means two customers submitted the same serial at once.
        raise AppError("already_registered", 409, "This mattress already has a registered warranty")

    # Mirror only — never a live read-through to GB Rewards. An unauthenticated
    # endpoint must not be able to make us call a third party once per request:
    # that hands anyone on the internet a lever on someone else's uptime and our
    # rate limits with them. A missing mirror row simply means the model is
    # unknown until an admin reconciles it.
    unit = session.execute(select(Unit).where(Unit.token == serial)).scalar_one_or_none()
    months = _unit_warranty_months(session, unit)
    warranty_months = (months if unit else None) or settings.default_warranty_months

    dealer = allocated_dealer(session, serial)

    # The stated purchase date is recorded as asked, however old. `needs_approval`
    # is ignored: this record is going to an admin regardless, and normalising the
    # date here would hide what the customer actually claimed from the person who
    # has to judge it.
    clock = decide_clock(warranty_months=warranty_months, invoice_date=purchase_date)

    # Fill-blanks-only, exactly as the dealer flow does — and here it is a
    # security property, not a courtesy. If a self-registration overwrote a
    # customer's stored details, anyone who knows a mobile number could rewrite
    # the name and address on every warranty that number owns.
    customer = _upsert_customer(
        session,
        phone=customer_phone,
        name=customer_name,
        address=customer_address,
        city=customer_city,
        state=customer_state,
        pincode=customer_pincode,
    )

    warranty = Warranty(
        serial=serial,
        unit_id=unit.id if unit else None,
        model_name=_unit_model_name(session, unit) if unit else None,
        model_code=None,
        warranty_months=warranty_months,
        # The dealer who should have done this. staff_id stays null: no person at
        # that shop touched this record, and pretending otherwise would put a
        # name against work nobody did.
        dealer_id=dealer.id if dealer else None,
        staff_id=None,
        customer_id=customer.id,
        invoice_ref=invoice_ref,
        invoice_date=purchase_date,
        warranty_start_date=clock.start_date,
        warranty_end_date=clock.end_date,
        backdate_days=clock.backdate_days,
        status="pending_review",
        source="customer_self",
        unit_unverified=unit is None,
        proof_file_key=proof_key,
    )
    session.add(warranty)

    try:
        session.flush()
    except IntegrityError as exc:
        # uq_warranties_live_serial. Two submissions for one serial raced past
        # the check above; the index is what actually prevents the duplicate.
        session.rollback()
        raise AppError(
            "already_registered", 409, "This mattress was just registered by someone else"
        ) from exc

    session.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event="self_registered",
            from_status=None,
            to_status="pending_review",
            actor_type="customer",
            actor_id=customer.id,
            event_metadata={
                "serial": serial,
                "requested_start_date": purchase_date.isoformat(),
                "backdate_days": clock.backdate_days,
                "invoice_ref": invoice_ref,
                "has_proof": bool(proof_key),
                # Unverified, and kept precisely because of that: when the serial
                # is allocated to nobody, the shop the customer names is the only
                # lead the compliance team has.
                "dealer_hint": dealer_hint,
                "allocated_dealer_code": dealer.code if dealer else None,
                # Anonymous write: the source address is what makes a burst of
                # fabricated submissions visible afterwards.
                "ip": ip,
            },
        )
    )
    session.flush()

    return SelfRegistration(warranty=warranty, dealer=dealer)


def pending_reviews(session: Session, *, limit: int = 100, offset: int = 0) -> list[Warranty]:
    """The non-compliance queue, newest first. Used by the admin approvals screen."""
    stmt = (
        select(Warranty)
        .where(Warranty.source == "customer_self", Warranty.status == "pending_review")
        .order_by(Warranty.created_at.desc())
        .limit(min(limit, 500))
        .offset(offset)
    )
    return list(session.execute(stmt).scalars())


def dealer_miss_counts(session: Session) -> dict[uuid.UUID, int]:
    """How many self-registrations name each dealer — the report, one line each."""
    rows = session.execute(
        select(Warranty.dealer_id, func.count())
        .where(Warranty.source == "customer_self", Warranty.dealer_id.is_not(None))
        .group_by(Warranty.dealer_id)
    ).all()
    return {row[0]: int(row[1]) for row in rows}
