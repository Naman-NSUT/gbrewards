import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardOut(BaseModel):
    total_users: int
    total_points_outstanding: int
    total_scans: int
    scans_today: int
    scans_this_week: int
    pending_redemptions: int
    products_in_catalog: int


class ScanUserBrief(BaseModel):
    id: uuid.UUID
    phone: str
    name: str


class ScanProductBrief(BaseModel):
    id: uuid.UUID
    name: str


class ScanFeedItem(BaseModel):
    id: uuid.UUID
    user: ScanUserBrief
    product: ScanProductBrief
    product_unit_id: uuid.UUID | None
    points: int
    scanned_at: datetime


class ScanFeedPage(BaseModel):
    items: list[ScanFeedItem]
    next_cursor: str | None = None


class AuditItem(BaseModel):
    id: uuid.UUID
    actor_admin_id: uuid.UUID | None
    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    metadata: dict[str, Any] | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditItem]
    next_cursor: str | None = None


class ScanDayPoint(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    scans: int
    points: int


class TopProduct(BaseModel):
    id: uuid.UUID
    name: str
    claimed: int


class DashboardAnalytics(BaseModel):
    scans_by_day: list[ScanDayPoint]
    redemptions_by_status: dict[str, int]
    top_products: list[TopProduct]
