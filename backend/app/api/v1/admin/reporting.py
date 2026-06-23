import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.admin import Admin
from app.schemas.dashboard import AuditPage, DashboardAnalytics, DashboardOut, ScanFeedPage
from app.services import reporting

router = APIRouter(tags=["admin-reporting"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> DashboardOut:
    return reporting.dashboard_summary(db)


@router.get("/analytics", response_model=DashboardAnalytics)
def analytics(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> DashboardAnalytics:
    return reporting.analytics(db)


@router.get("/scans", response_model=ScanFeedPage)
def scans(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    product_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> ScanFeedPage:
    return reporting.scan_feed(
        db,
        product_id=product_id,
        user_id=user_id,
        from_=from_,
        to=to,
        cursor=cursor,
        limit=limit,
    )


@router.get("/audit", response_model=AuditPage)
def audit(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    entity: str | None = None,
    actor: uuid.UUID | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditPage:
    return reporting.audit_feed(
        db,
        entity=entity,
        actor=actor,
        from_=from_,
        to=to,
        cursor=cursor,
        limit=limit,
    )
