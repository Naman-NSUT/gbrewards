import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str
    address: str | None = None
    is_verified: bool
    balance: int
    available: int
    last_active_at: datetime | None = None


class MeUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=500)
