import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.profile import AddressLine, City, Dob, Gender, Pincode, State


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    dob: date | None = None
    gender: str | None = None
    is_verified: bool
    balance: int
    available: int
    last_active_at: datetime | None = None


class MeUpdateIn(BaseModel):
    """PATCH semantics — every field optional; only what is sent gets applied."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: AddressLine | None = None
    city: City | None = None
    state: State | None = None
    pincode: Pincode | None = None
    dob: Dob | None = None
    gender: Gender | None = None
