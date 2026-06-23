import uuid
from datetime import datetime

from pydantic import BaseModel


class ScanClaimIn(BaseModel):
    token: str


class ProductBrief(BaseModel):
    id: uuid.UUID
    name: str
    points_value: int


class ScanClaimOut(BaseModel):
    product: ProductBrief
    points_awarded: int
    balance: int
    available: int
    claimed_at: datetime
    idempotent: bool
