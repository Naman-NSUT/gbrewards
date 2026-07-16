import uuid

from pydantic import BaseModel, ConfigDict

# Broker-facing reward/banner output reuses the admin shapes verbatim.
from app.schemas.admin import BannerOut, ContentDocOut, RewardOut

__all__ = [
    "BannerOut",
    "ContentDocOut",
    "FaqPublicOut",
    "ProductPointsOut",
    "RewardOut",
]


class FaqPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer: str
    sort_order: int


class ProductPointsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    points_value: int
