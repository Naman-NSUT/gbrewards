import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RedemptionCreateIn(BaseModel):
    points: int | None = Field(default=None, gt=0)
    reward_id: uuid.UUID | None = None
    # How many of the reward to take. Only meaningful with reward_id; a raw
    # points request already names its own amount. Older app builds omit it, so
    # the default has to stay 1.
    quantity: int = Field(default=1, ge=1, le=999)


class RedemptionActionIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class RedemptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    points: int
    quantity: int
    status: str
    note: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    reward_id: uuid.UUID | None = None


class RedemptionUserBrief(BaseModel):
    id: uuid.UUID
    phone: str
    name: str


class RedemptionRewardBrief(BaseModel):
    id: uuid.UUID
    title: str


class RedemptionAdminOut(RedemptionOut):
    user: RedemptionUserBrief
    reward: RedemptionRewardBrief | None = None
