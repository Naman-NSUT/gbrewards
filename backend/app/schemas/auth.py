import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

PHONE_PATTERN = r"^\+[1-9]\d{7,14}$"


class OtpRequestIn(BaseModel):
    """Step 1: upsert the broker by phone (with name + address) and send an OTP."""

    phone: str = Field(pattern=PHONE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)


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
    is_verified: bool
    last_active_at: datetime | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut | None = None
