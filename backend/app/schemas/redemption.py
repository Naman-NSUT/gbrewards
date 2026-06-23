import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RedemptionCreateIn(BaseModel):
    points: int = Field(gt=0)


class RedemptionActionIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class RedemptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    points: int
    status: str
    note: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class RedemptionUserBrief(BaseModel):
    id: uuid.UUID
    phone: str
    name: str


class RedemptionAdminOut(RedemptionOut):
    user: RedemptionUserBrief
