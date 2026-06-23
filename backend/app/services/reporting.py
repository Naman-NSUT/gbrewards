"""Admin reporting: dashboard tiles, scan feed, audit trail (FR-D1/FR-D3)."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date as SADate
from sqlalchemy import cast, func, select, tuple_
from sqlalchemy.orm import Session

from app.api.pagination import decode_cursor, encode_cursor
from app.models.audit_log import AuditLog
from app.models.ledger_entry import LedgerEntry
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.models.redemption_request import RedemptionRequest
from app.models.user import User
from app.schemas.dashboard import (
    AuditItem,
    AuditPage,
    DashboardAnalytics,
    DashboardOut,
    ScanDayPoint,
    ScanFeedItem,
    ScanFeedPage,
    ScanProductBrief,
    ScanUserBrief,
    TopProduct,
)
from app.services.ledger import LedgerType

SCAN_CREDIT = str(LedgerType.SCAN_CREDIT)


def _count(db: Session, stmt) -> int:  # type: ignore[no-untyped-def]
    return int(db.execute(stmt).scalar_one())


def dashboard_summary(db: Session) -> DashboardOut:
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    scan_filter = LedgerEntry.type == SCAN_CREDIT

    return DashboardOut(
        total_users=_count(db, select(func.count()).select_from(User)),
        total_points_outstanding=int(
            db.execute(select(func.coalesce(func.sum(LedgerEntry.amount), 0))).scalar_one()
        ),
        total_scans=_count(db, select(func.count()).select_from(LedgerEntry).where(scan_filter)),
        scans_today=_count(
            db,
            select(func.count())
            .select_from(LedgerEntry)
            .where(scan_filter, LedgerEntry.created_at >= today_start),
        ),
        scans_this_week=_count(
            db,
            select(func.count())
            .select_from(LedgerEntry)
            .where(scan_filter, LedgerEntry.created_at >= week_start),
        ),
        pending_redemptions=_count(
            db,
            select(func.count())
            .select_from(RedemptionRequest)
            .where(RedemptionRequest.status == "pending"),
        ),
        products_in_catalog=_count(db, select(func.count()).select_from(Product)),
    )


def analytics(db: Session, *, days: int = 14) -> DashboardAnalytics:
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)

    # scans (+ points) grouped by UTC day
    day_col = cast(LedgerEntry.created_at, SADate)
    rows = db.execute(
        select(day_col, func.count(), func.coalesce(func.sum(LedgerEntry.amount), 0))
        .where(LedgerEntry.type == SCAN_CREDIT, LedgerEntry.created_at >= start_dt)
        .group_by(day_col)
    ).all()
    by_day: dict[date, tuple[int, int]] = {d: (int(c), int(p)) for d, c, p in rows}
    scans_by_day = [
        ScanDayPoint(
            date=(d := start + timedelta(days=i)).isoformat(),
            scans=by_day.get(d, (0, 0))[0],
            points=by_day.get(d, (0, 0))[1],
        )
        for i in range(days)
    ]

    status_rows = db.execute(
        select(RedemptionRequest.status, func.count()).group_by(RedemptionRequest.status)
    ).all()
    redemptions_by_status = {status: int(count) for status, count in status_rows}

    top_rows = db.execute(
        select(Product.id, Product.name, func.count(ProductUnit.id))
        .join(ProductUnit, ProductUnit.product_id == Product.id)
        .where(ProductUnit.status == "claimed")
        .group_by(Product.id, Product.name)
        .order_by(func.count(ProductUnit.id).desc())
        .limit(5)
    ).all()
    top_products = [
        TopProduct(id=pid, name=name, claimed=int(claimed)) for pid, name, claimed in top_rows
    ]

    return DashboardAnalytics(
        scans_by_day=scans_by_day,
        redemptions_by_status=redemptions_by_status,
        top_products=top_products,
    )


def scan_feed(
    db: Session,
    *,
    product_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    from_: datetime | None,
    to: datetime | None,
    cursor: str | None,
    limit: int,
) -> ScanFeedPage:
    stmt = (
        select(LedgerEntry, ProductUnit, Product, User)
        .join(ProductUnit, LedgerEntry.product_unit_id == ProductUnit.id)
        .join(Product, ProductUnit.product_id == Product.id)
        .join(User, LedgerEntry.user_id == User.id)
        .where(LedgerEntry.type == SCAN_CREDIT)
    )
    if product_id is not None:
        stmt = stmt.where(ProductUnit.product_id == product_id)
    if user_id is not None:
        stmt = stmt.where(LedgerEntry.user_id == user_id)
    if from_ is not None:
        stmt = stmt.where(LedgerEntry.created_at >= from_)
    if to is not None:
        stmt = stmt.where(LedgerEntry.created_at <= to)
    if cursor is not None:
        c_created, c_id = decode_cursor(cursor)
        stmt = stmt.where(tuple_(LedgerEntry.created_at, LedgerEntry.id) < (c_created, c_id))

    stmt = stmt.order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc()).limit(limit + 1)
    rows = db.execute(stmt).all()

    next_cursor = None
    if len(rows) > limit:
        last_entry = rows[limit - 1][0]
        next_cursor = encode_cursor(last_entry.created_at, last_entry.id)
        rows = rows[:limit]

    items = [
        ScanFeedItem(
            id=entry.id,
            user=ScanUserBrief(id=user.id, phone=user.phone, name=user.name),
            product=ScanProductBrief(id=product.id, name=product.name),
            product_unit_id=unit.id,
            points=entry.amount,
            scanned_at=entry.created_at,
        )
        for entry, unit, product, user in rows
    ]
    return ScanFeedPage(items=items, next_cursor=next_cursor)


def audit_feed(
    db: Session,
    *,
    entity: str | None,
    actor: uuid.UUID | None,
    from_: datetime | None,
    to: datetime | None,
    cursor: str | None,
    limit: int,
) -> AuditPage:
    stmt = select(AuditLog)
    if entity is not None:
        stmt = stmt.where(AuditLog.entity_type == entity)
    if actor is not None:
        stmt = stmt.where(AuditLog.actor_admin_id == actor)
    if from_ is not None:
        stmt = stmt.where(AuditLog.created_at >= from_)
    if to is not None:
        stmt = stmt.where(AuditLog.created_at <= to)
    if cursor is not None:
        c_created, c_id = decode_cursor(cursor)
        stmt = stmt.where(tuple_(AuditLog.created_at, AuditLog.id) < (c_created, c_id))

    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1)
    rows = list(db.execute(stmt).scalars().all())

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.created_at, last.id)
        rows = rows[:limit]

    items = [
        AuditItem(
            id=row.id,
            actor_admin_id=row.actor_admin_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            metadata=row.audit_metadata,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return AuditPage(items=items, next_cursor=next_cursor)
