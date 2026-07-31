import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.profile import AddressLine, City, Dob, Gender, Pincode, State

PHONE_PATTERN = r"^\+[1-9]\d{7,14}$"


class OtpRequestIn(BaseModel):
    """Step 1: upsert the broker's profile by phone and send an OTP.

    Only phone, name and address are mandatory at the API boundary. The rest are
    optional so that app builds predating them keep working and so a partial
    profile is never blanked out — the current app collects all of them and the
    upsert fills in whatever it sends.
    """

    phone: str = Field(pattern=PHONE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    address: AddressLine
    city: City | None = None
    state: State | None = None
    pincode: Pincode | None = None
    dob: Dob | None = None
    gender: Gender | None = None


class OtpRequestOut(BaseModel):
    sent: bool = True
    resend_in: int


class OtpVerifyIn(BaseModel):
    """Step 2: verify the SMS code and issue tokens."""

    phone: str = Field(pattern=PHONE_PATTERN)
    code: str = Field(min_length=4, max_length=8)


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
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
    last_active_at: datetime | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut | None = None
