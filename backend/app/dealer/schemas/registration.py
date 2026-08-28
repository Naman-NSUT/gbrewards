import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.dealer.schemas.common import Base, PhoneMixin


class RegisterIn(PhoneMixin, Base):
    # What was sold, picked from the dealer's product list. Nothing is scanned
    # any more, so this is the only thing that says which mattress this is — and,
    # through the product's point rate, what the registration is worth.
    product_id: uuid.UUID
    customer_phone: str = Field(min_length=6, max_length=20)
    customer_name: str = Field(min_length=1, max_length=200)
    # The dealer's own invoice number, and now the only thing stopping the same
    # sale being registered twice: one live warranty per (dealer, invoice_ref),
    # enforced by uq_warranties_live_dealer_invoice.
    #
    # Stripped, because the database compares with lower() and not trim(): a
    # trailing space would otherwise be a second, free copy of the same invoice.
    invoice_ref: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    invoice_date: date | None = None
    customer_address: str | None = Field(default=None, max_length=400)
    customer_city: str | None = Field(default=None, max_length=100)
    customer_state: str | None = Field(default=None, max_length=100)
    customer_pincode: str | None = Field(default=None, max_length=10)


class WarrantyOut(Base):
    id: uuid.UUID
    # Null on everything registered since the dropdown replaced the scanner.
    # Historic warranties still carry the code printed under their QR.
    serial: str | None
    model_name: str | None
    warranty_months: int
    warranty_start_date: date
    warranty_end_date: date
    status: str
    invoice_ref: str | None
    invoice_date: date | None
    backdate_days: int
    unit_unverified: bool
    registered_at: datetime


class CustomerBrief(Base):
    name: str
    phone: str


class RegisterOut(Base):
    warranty: WarrantyOut
    customer: CustomerBrief
    points_awarded: int
    balance: int
    # True when this response replays an earlier identical submission.
    idempotent: bool
    # Present when the sale completed without upstream verification, so the app
    # can show a quiet "we'll confirm this shortly" rather than pretending.
    unit_unverified: bool
