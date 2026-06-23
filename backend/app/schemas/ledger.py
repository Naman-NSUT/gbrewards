import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: int
    type: str
    note: str | None = None
    product_unit_id: uuid.UUID | None = None
    redemption_id: uuid.UUID | None = None
    created_at: datetime


class LedgerPage(BaseModel):
    items: list[LedgerEntryOut]
    next_cursor: str | None = None
