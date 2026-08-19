import uuid
from datetime import date, datetime

from pydantic import Field

from app.dealer.schemas.common import Base, PhoneMixin


class RegisterIn(PhoneMixin, Base):
    # Whatever the camera decoded. Normalised server-side — the client must not
    # be trusted to parse the QR payload, because the payload format is owned by
    # another system and may change.
    serial: str = Field(min_length=1, max_length=200)
    customer_phone: str = Field(min_length=6, max_length=20)
    customer_name: str = Field(min_length=1, max_length=200)
    invoice_ref: str = Field(min_length=1, max_length=120)
    invoice_date: date | None = None
    customer_address: str | None = Field(default=None, max_length=400)
    customer_city: str | None = Field(default=None, max_length=100)
    customer_state: str | None = Field(default=None, max_length=100)
    customer_pincode: str | None = Field(default=None, max_length=10)


class WarrantyOut(Base):
    id: uuid.UUID
    serial: str
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


class UnitPreviewOut(Base):
    """What the app shows between scanning and typing customer details."""

    serial: str
    model_name: str | None
    warranty_months: int
    registerable: bool
    reason: str | None = None
    already_registered: bool = False
