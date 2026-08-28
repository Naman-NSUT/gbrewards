"""Warranty registration — the transaction the whole product is built around.

Everything here happens in ONE database transaction, or none of it does:

    resolve product → upsert customer → create warranty → credit points
    → write the warranty event → queue the SMS

The points credit is in the same transaction as the warranty, so a crash between
them is impossible rather than merely unlikely. The SMS is queued as a row inside
the transaction but SENT outside it, because a slow provider must not hold a
database transaction open while a dealer waits, and an SMS failure must not roll
back a completed sale.

Nothing is scanned any more. The dealer picks the product from a dropdown and
types their own invoice number, which moves the entire anti-farming burden onto
that number. A serial was a fact about a physical object: the factory printed a
finite number of them and each one could pay exactly once, so the total payout
was capped by manufacturing. An invoice number is a string a dealer types, and
without a uniqueness rule the same product registered five hundred times pays
five hundred times. So one live warranty per (dealer, invoice number) is not a
tidiness rule — it is the cap, and it lives in the database because two
submissions of the same invoice arriving at once would both pass a check written
in Python.

Abuse resistance is not a later hardening pass; it is the shape of this function:
  * one live warranty per dealer invoice number                 (DB partial index)
  * a warranty can be paid for only once                        (DB partial index)
  * a retry returns the original result                         (idempotency)
  * the clock is server-derived                                 (warranty_dates)
  * velocity limits cap a compromised login                     (rate limiter)
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import DealerStaff
from app.dealer.models.product import DealerProduct
from app.dealer.models.warranty import LIVE_STATUSES, Warranty, WarrantyEvent
from app.dealer.services import ledger
from app.dealer.services.warranty_dates import decide_clock

logger = get_logger(__name__)

_DUPLICATE_INVOICE_INDEX = "uq_warranties_live_dealer_invoice"


@dataclass
class RegistrationResult:
    warranty: Warranty
    points_awarded: int
    balance: int
    # Always False here. A genuine double-tap is caught one layer up by the
    # Idempotency-Key header, which replays the original response; a resubmitted
    # invoice number is a duplicate and is refused, not replayed. Kept so the
    # response shape the app parses does not change.
    idempotent: bool
    # Dead flag: it meant "we could not verify this serial against the factory".
    # There is no serial to verify. Always False.
    unit_unverified: bool


def _resolve_product(session: Session, product_id: uuid.UUID) -> DealerProduct:
    """The product the dealer picked. It decides both the warranty and the money.

    An inactive product is refused rather than quietly registered: deactivating a
    product is how the client stops a discontinued model being sold, and honouring
    a stale dropdown would let an app that has not refreshed its list keep
    registering — and keep being paid for — a model nobody is selling.
    """
    product = session.get(DealerProduct, product_id)
    if product is None or not product.is_active:
        raise AppError(
            "invalid_product",
            404,
            "That product is not available. Refresh the list and pick it again.",
        )
    return product


def _reject_duplicate_invoice(
    session: Session, *, dealer_id: uuid.UUID | None, invoice: str
) -> None:
    """Refuse a bill this dealer has already registered.

    Checked explicitly so the ordinary case — a dealer re-typing a bill they
    already entered — gets a clear answer instead of an IntegrityError.
    uq_warranties_live_dealer_invoice is still the real guarantee, because this
    SELECT cannot see a row a concurrent request has not committed yet; this is
    only the good error message.

    Case-insensitive, matching the index exactly. If this compared with == while
    the index compared with lower(), "inv-1" would sail past here and come back
    as the same 409 from the flush — the same answer by a worse route, and a
    silent invitation for the two rules to drift apart.
    """
    existing = session.execute(
        select(Warranty.id).where(
            Warranty.dealer_id == dealer_id,
            func.lower(Warranty.invoice_ref) == invoice.lower(),
            Warranty.status.in_(LIVE_STATUSES),
        )
    ).first()
    if existing is not None:
        raise AppError(
            "duplicate_invoice",
            409,
            "This invoice number is already registered. Each sale needs its own invoice.",
        )


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
    product_id: uuid.UUID,
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
    dealer_id = staff.dealer_id

    # Trimmed here as well as in the schema, because this function is also called
    # directly. The index compares lower(invoice_ref) and nothing else, so
    # "INV-7 " left untrimmed would be a second, payable copy of "INV-7".
    invoice = invoice_ref.strip()

    product = _resolve_product(session, product_id)
    _reject_duplicate_invoice(session, dealer_id=dealer_id, invoice=invoice)

    clock = decide_clock(
        warranty_months=product.warranty_months, invoice_date=invoice_date, now=now
    )

    customer = _upsert_customer(
        session,
        phone=customer_phone,
        name=customer_name,
        address=customer_address,
        city=customer_city,
        state=customer_state,
        pincode=customer_pincode,
    )

    if clock.needs_approval:
        status = "pending_backdate"
    elif settings.require_customer_confirmation:
        status = "pending_confirmation"
    else:
        status = "active"

    warranty = Warranty(
        # Nothing was scanned, so there is no code to record. Historic rows keep
        # theirs; NULLs do not collide in uq_warranties_live_serial, so the old
        # guarantee still protects the old rows.
        serial=None,
        unit_id=None,
        # Frozen at sale time: the product's warranty length and point rate are
        # what this sale was made under, and a later catalogue edit must not
        # rewrite a warranty that has already been sold and paid for.
        product_id=product.id,
        model_name=product.name,
        model_code=product.model_code,
        warranty_months=product.warranty_months,
        dealer_id=dealer_id,
        staff_id=staff.id,
        customer_id=customer.id,
        invoice_ref=invoice,
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
        # Two devices submitted the same invoice at the same instant and both got
        # past the SELECT above. uq_warranties_live_dealer_invoice is what
        # actually stops the second one being paid; this turns it into the same
        # clean 409 the check would have given. Any other integrity failure is a
        # real bug and must not be dressed up as a duplicate invoice.
        session.rollback()
        if _DUPLICATE_INVOICE_INDEX not in str(exc.orig):
            raise
        raise AppError(
            "duplicate_invoice",
            409,
            "This invoice number was just registered. Each sale needs its own invoice.",
        ) from exc

    points = 0
    # Per product: a premium mattress is worth more to register than an entry
    # model, exactly as worker scan points already vary by product.
    rate = ledger.current_rate(session, product_id=product.id)
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
            metadata={"invoice_ref": invoice},
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
                "product_id": str(product.id),
                "invoice_ref": invoice,
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
