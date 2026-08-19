"""The audit feed: who changed what, when, and why.

Distinct from a warranty's own event history — this is the cross-cutting record
that answers 'why does this dealer have 300 points they did not earn?' months
later. Newest first, because the question is almost always about something that
just happened.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_dealer_admin, get_db
from app.dealer.api.admin._common import Pagination, count_of, day_window, like, pagination
from app.dealer.models.admin import DealerAdmin as Admin
from app.dealer.models.audit_log import DealerAuditLog as AuditLog
from app.dealer.models.dealer import DealerStaff
from app.dealer.schemas.admin import AuditOut, Paginated

router = APIRouter(tags=["admin-audit"])


@router.get("/audit", response_model=Paginated[AuditOut])
def list_audit(
    actor_type: str | None = Query(
        default=None, pattern="^(admin|dealer_staff|customer|system)$"
    ),
    actor_id: uuid.UUID | None = None,
    action: str | None = Query(default=None, max_length=60),
    entity_type: str | None = Query(default=None, max_length=40),
    entity_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=200, description="matches the reason text"),
    date_from: date | None = None,
    date_to: date | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[AuditOut]:
    # Actor ids are polymorphic and deliberately not foreign keys (an audit row
    # must outlive the actor's row), so the name is resolved by two outer joins
    # rather than a relationship. A UUID alone is unreadable on this screen.
    stmt = (
        select(AuditLog, Admin.name, DealerStaff.name)
        .outerjoin(Admin, Admin.id == AuditLog.actor_id)
        .outerjoin(DealerStaff, DealerStaff.id == AuditLog.actor_id)
    )
    if actor_type:
        stmt = stmt.where(AuditLog.actor_type == actor_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if q:
        term = like(q)
        stmt = stmt.where(or_(AuditLog.reason.ilike(term), AuditLog.actor_label.ilike(term)))

    start, end = day_window(date_from, date_to)
    if start is not None:
        stmt = stmt.where(AuditLog.created_at >= start)
    if end is not None:
        stmt = stmt.where(AuditLog.created_at < end)

    total = count_of(db, stmt)
    rows = db.execute(
        stmt.order_by(AuditLog.created_at.desc()).limit(page.limit).offset(page.offset)
    ).all()

    return Paginated[AuditOut](
        items=[
            AuditOut(
                id=log.id,
                actor_type=log.actor_type,
                actor_id=log.actor_id,
                actor_name=admin_name or staff_name,
                actor_label=log.actor_label,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                reason=log.reason,
                metadata=log.audit_metadata,
                ip=log.ip,
                created_at=log.created_at,
            )
            for log, admin_name, staff_name in rows
        ],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/audit/filters")
def audit_filters(
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> dict[str, list[str]]:
    """The action and entity values actually present, for the filter dropdowns.

    Read from the data rather than from a hardcoded list, so an action added by
    a later feature appears in the filter without anyone remembering to add it.
    """
    actions = db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action)).scalars()
    entities = db.execute(
        select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
    ).scalars()
    return {
        "actions": [a for a in actions if a],
        "entity_types": [e for e in entities if e],
    }


@router.get("/audit/entity/{entity_type}/{entity_id}", response_model=list[AuditOut])
def entity_history(
    entity_type: str,
    entity_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> list[AuditOut]:
    """Everything ever done to one record — the 'History' tab on any detail page."""
    rows = db.execute(
        select(AuditLog, Admin.name, DealerStaff.name)
        .outerjoin(Admin, Admin.id == AuditLog.actor_id)
        .outerjoin(DealerStaff, DealerStaff.id == AuditLog.actor_id)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        AuditOut(
            id=log.id,
            actor_type=log.actor_type,
            actor_id=log.actor_id,
            actor_name=admin_name or staff_name,
            actor_label=log.actor_label,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            reason=log.reason,
            metadata=log.audit_metadata,
            ip=log.ip,
            created_at=log.created_at,
        )
        for log, admin_name, staff_name in rows
    ]
