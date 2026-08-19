"""Schemas for the public, unauthenticated API — and the redaction rules.

Everything shaped here is served to anyone on the internet who can type a URL, so
redaction is a property of the schema rather than a decision each router makes:
there is exactly one way to render a warranty publicly, `redact()`, and it never
emits a customer's real name, full phone, address, or the dealer's contact
details. A route that forgets to redact is not possible, because the public
response models cannot carry those fields at all.

Masking is FIXED WIDTH. "A**** K****" for any name and "98****5678" for any
number: a mask that mirrored the real length would leak the length, and a
four-character surname is a much smaller guessing space than an unknown one.
"""

import re
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from app.dealer.schemas.common import Base, PhoneMixin

if TYPE_CHECKING:  # imported for typing only — schemas must not depend on the ORM
    from app.dealer.models.dealer import Dealer
    from app.dealer.models.warranty import Warranty

_MASK = "****"
_NON_DIGITS = re.compile(r"\D")


def mask_name(name: str) -> str:
    """'Anil Kumar' -> 'A**** K****'.

    Enough for the person who owns the record to recognise it, not enough for
    someone who photographed a serial in a shop to learn who the buyer is.
    """
    parts = [p for p in (name or "").split() if p][:3]
    if not parts:
        return _MASK
    return " ".join(f"{part[0].upper()}{_MASK}" for part in parts)


def mask_phone(phone: str) -> str:
    """'+919812345678' -> '98****5678'.

    The last four digits are what a customer recognises as theirs and what the
    support desk asks for; the middle four are what would make the number
    dialable, so those are the ones that go.
    """
    digits = _NON_DIGITS.sub("", phone or "")
    if len(digits) < 6:
        return _MASK
    local = digits[-10:]
    return f"{local[:2]}{_MASK}{local[-4:]}"


class MaskedCustomerOut(Base):
    name: str
    phone: str


class SellingDealerOut(Base):
    """Shop name and city only.

    A customer needs to know which shop sold them the mattress. Nobody on a
    public endpoint needs the dealer's phone, email, GST number or address, and
    publishing them would turn this into a scrape-able dealer directory for
    whoever wants to poach the client's retail network.
    """

    name: str
    city: str | None = None


class RedactedWarrantyOut(Base):
    id: uuid.UUID
    serial: str
    model_name: str | None
    # Derived via warranty_svc.display_status, so an out-of-date row still reads
    # 'expired' to the customer rather than 'active'.
    status: str
    warranty_months: int
    warranty_start_date: date
    warranty_end_date: date
    registered_at: datetime
    # 'dealer' | 'customer_self' | 'admin' | 'migration'. The customer is told
    # who created the record, because "you registered this yourself, it is with
    # our team" is a different message from "your dealer registered this".
    source: str
    customer: MaskedCustomerOut
    dealer: SellingDealerOut | None = None


def redact(warranty: "Warranty", *, dealer: "Dealer | None" = None) -> RedactedWarrantyOut:
    """The only public rendering of a warranty."""
    # Imported inside the function: this module is a schema module and must stay
    # importable without pulling the service layer in behind it.
    from app.dealer.services import warranty as warranty_svc

    return RedactedWarrantyOut(
        id=warranty.id,
        serial=warranty.serial,
        model_name=warranty.model_name,
        status=warranty_svc.display_status(warranty),
        warranty_months=warranty.warranty_months,
        warranty_start_date=warranty.warranty_start_date,
        warranty_end_date=warranty.warranty_end_date,
        registered_at=warranty.registered_at,
        source=warranty.source,
        customer=MaskedCustomerOut(
            name=mask_name(warranty.customer.name),
            phone=mask_phone(warranty.customer.phone),
        ),
        dealer=SellingDealerOut(name=dealer.name, city=dealer.city) if dealer else None,
    )


# --- Lookup ----------------------------------------------------------------


class LookupIn(PhoneMixin, Base):
    phone: str | None = Field(default=None, max_length=20)
    serial: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _exactly_one(self) -> "LookupIn":
        if bool(self.phone) == bool(self.serial):
            raise ValueError("Search by either a mobile number or a serial number, not both")
        return self


class LookupOut(Base):
    results: list[RedactedWarrantyOut]
    # Set when there is nothing to show, so the frontend has copy to render
    # rather than inventing its own.
    message: str | None = None
    # Drives the "register it yourself" call to action. Always true on an empty
    # result: it must not double as an oracle for "this serial exists".
    can_self_register: bool = False


# --- Self-registration -----------------------------------------------------


class SelfRegistrationIn(PhoneMixin, Base):
    """The typed part of the self-registration form.

    Applied by hand in the router rather than bound as a FastAPI `Form()` model —
    see the comment there. The file is not a field: this model stays free of any
    value that cannot be serialised into an error response.
    """

    serial: str = Field(min_length=1, max_length=200)
    customer_phone: str = Field(min_length=6, max_length=20)
    customer_name: str = Field(min_length=1, max_length=200)
    # Required, unlike the dealer flow: the entire point of this form is to
    # recover the real sale date that the dealer never recorded.
    purchase_date: date
    invoice_ref: str | None = Field(default=None, max_length=120)
    # Free text: which shop they bought it from. When the serial is not
    # allocated to anyone, this is the only lead the compliance team has, so it
    # is kept even though it is unverified.
    dealer_hint: str | None = Field(default=None, max_length=200)
    customer_address: str | None = Field(default=None, max_length=400)
    customer_city: str | None = Field(default=None, max_length=100)
    customer_state: str | None = Field(default=None, max_length=100)
    customer_pincode: str | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def _sane_purchase_date(self) -> "SelfRegistrationIn":
        from app.dealer.services.warranty_dates import business_today

        today = business_today()
        if self.purchase_date > today:
            raise ValueError("The purchase date cannot be in the future")
        # A GoodBed warranty runs five years. A date older than ten is a typo
        # (usually the wrong year), and accepting it would create a warranty that
        # is already expired on arrival with no way to tell the two apart.
        if (today - self.purchase_date).days > 3660:
            raise ValueError("That purchase date is too old — check the year on your invoice")
        return self


class SelfRegistrationOut(Base):
    # 'submitted' — created and queued for review.
    # 'already_registered' — a live warranty exists on this serial; nothing new
    # was created and the existing (redacted) record is returned.
    status: str
    warranty: RedactedWarrantyOut
    message: str


# --- Claims ----------------------------------------------------------------


class ClaimIn(PhoneMixin, Base):
    serial: str = Field(min_length=1, max_length=200)
    # The possession check. A claim can only be raised by someone who knows the
    # number on the record, not by anyone who can read a serial off a label.
    phone: str = Field(min_length=6, max_length=20)
    issue_type: str | None = Field(default=None, max_length=60)
    description: str = Field(min_length=10, max_length=2000)


class ClaimStatusIn(PhoneMixin, Base):
    reference: str = Field(min_length=4, max_length=16)
    phone: str = Field(min_length=6, max_length=20)


class ClaimOut(Base):
    reference: str
    status: str
    issue_type: str | None
    description: str
    created_at: datetime
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    warranty: RedactedWarrantyOut
    message: str


# --- Confirm / dispute -----------------------------------------------------


class Last4In(Base):
    # Lightweight possession check on top of the warranty id in the SMS link: a
    # forwarded or leaked link is not, on its own, enough to act on a record.
    # [0-9] rather than \d, which also matches non-ASCII digits that would then
    # blow up the constant-time comparison in the router.
    last4: str = Field(min_length=4, max_length=4, pattern=r"^[0-9]{4}$")


class DisputeIn(Last4In):
    note: str | None = Field(default=None, max_length=1000)


class WarrantyViewOut(Base):
    warranty: RedactedWarrantyOut
    # True while the record is waiting for this customer to confirm, so the page
    # knows whether to show the confirm/dispute buttons prominently.
    awaiting_confirmation: bool
    already_confirmed: bool


class CustomerActionOut(Base):
    warranty: RedactedWarrantyOut
    message: str
