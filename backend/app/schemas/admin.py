import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ledger import LedgerEntryOut


class AdminLoginIn(BaseModel):
    # Accept a plain username or an email — matched verbatim against admins.email.
    email: str
    password: str


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None = None
    role: str


class AdminTokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    admin: AdminOut


class AdminRefreshIn(BaseModel):
    refresh_token: str


class AdminProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=200)


class AdminPasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    terms: str | None = None
    points_value: int = Field(ge=0)
    is_active: bool = True


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    terms: str | None = None
    points_value: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    terms: str | None = None
    points_value: int
    is_active: bool
    created_at: datetime


class ProductWithCounts(ProductOut):
    units_generated: int
    units_claimed: int
    units_available: int
    units_void: int


class BatchCreateIn(BaseModel):
    quantity: int = Field(gt=0, le=10000)
    label: str | None = Field(default=None, max_length=200)


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    label: str | None = None
    created_at: datetime


class OrderItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0, le=10000)


class OrderCreateIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)
    label: str | None = Field(default=None, max_length=200)


class OrderBatchLine(BaseModel):
    batch_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: int


class OrderCreateOut(BaseModel):
    label: str | None = None
    total_units: int
    batches: list[OrderBatchLine]


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    token: str
    status: str
    batch_id: uuid.UUID | None = None
    claimed_by_user_id: uuid.UUID | None = None
    claimed_at: datetime | None = None
    created_at: datetime


class UnitDetailOut(UnitOut):
    product_name: str | None = None
    claimed_by_name: str | None = None
    claimed_by_phone: str | None = None
    history: list[LedgerEntryOut] = []


class ReactivateOut(BaseModel):
    unit: UnitOut
    reversed_points: int
    user_id: uuid.UUID


class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str
    is_verified: bool
    is_active: bool
    balance: int
    total_earned: int
    last_active_at: datetime | None = None
    created_at: datetime


class AdminUserListPage(BaseModel):
    items: list[AdminUserListItem]
    next_cursor: str | None = None


class AdminUserDetail(AdminUserListItem):
    available: int


class AdjustIn(BaseModel):
    points: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class UserStatusIn(BaseModel):
    is_active: bool


class RewardIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    points_cost: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    sort_order: int = 0


class RewardUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    points_cost: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    sort_order: int | None = None


class RewardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = None
    points_cost: int
    image_url: str | None = None
    is_active: bool
    sort_order: int
    created_at: datetime


class FaqIn(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    sort_order: int = 0
    is_published: bool = True


class FaqUpdateIn(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    answer: str | None = Field(default=None, min_length=1)
    sort_order: int | None = None
    is_published: bool | None = None


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer: str
    sort_order: int
    is_published: bool
    created_at: datetime


class ContentDocUpsertIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str


class ContentDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    title: str
    body: str
    updated_at: datetime
