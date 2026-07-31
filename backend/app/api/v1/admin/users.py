import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select, tuple_
from sqlalchemy.orm import Session

from app.api.pagination import decode_cursor, encode_cursor, ledger_page
from app.core.deps import get_current_admin, get_db
from app.core.errors import AppError
from app.models.admin import Admin
from app.models.ledger_entry import LedgerEntry
from app.models.user import User
from app.schemas.admin import (
    AdjustIn,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserListPage,
    UserStatusIn,
)
from app.schemas.ledger import LedgerPage
from app.services import ledger
from app.services.audit import record_audit
from app.services.ledger import LedgerType

router = APIRouter(tags=["admin-users"])


def _get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("user_not_found", 404, "Unknown user")
    return user


def _detail(db: Session, user: User) -> AdminUserDetail:
    return AdminUserDetail(
        id=user.id,
        phone=user.phone,
        name=user.name,
        is_verified=user.is_verified,
        is_active=user.is_active,
        balance=ledger.balance(db, user.id),
        total_earned=ledger.total_earned(db, user.id),
        available=ledger.available(db, user.id),
        last_active_at=user.last_active_at,
        created_at=user.created_at,
        address=user.address,
        city=user.city,
        state=user.state,
        pincode=user.pincode,
        dob=user.dob,
        gender=user.gender,
    )


@router.get("/users", response_model=AdminUserListPage)
def list_users(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AdminUserListPage:
    balance_col = func.coalesce(func.sum(LedgerEntry.amount), 0)
    earned_col = func.coalesce(
        func.sum(case((LedgerEntry.amount > 0, LedgerEntry.amount), else_=0)), 0
    )
    agg = (
        select(
            LedgerEntry.user_id.label("user_id"),
            balance_col.label("balance"),
            earned_col.label("earned"),
        )
        .group_by(LedgerEntry.user_id)
        .subquery()
    )

    stmt = select(
        User,
        func.coalesce(agg.c.balance, 0),
        func.coalesce(agg.c.earned, 0),
    ).outerjoin(agg, User.id == agg.c.user_id)

    if q:
        stmt = stmt.where(or_(User.name.ilike(f"%{q}%"), User.phone.ilike(f"%{q}%")))
    if cursor is not None:
        created_at, uid = decode_cursor(cursor)
        stmt = stmt.where(tuple_(User.created_at, User.id) < (created_at, uid))

    stmt = stmt.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
    rows = db.execute(stmt).all()

    next_cursor = None
    if len(rows) > limit:
        last_user = rows[limit - 1][0]
        next_cursor = encode_cursor(last_user.created_at, last_user.id)
        rows = rows[:limit]

    items = [
        AdminUserListItem(
            id=user.id,
            phone=user.phone,
            name=user.name,
            is_verified=user.is_verified,
            is_active=user.is_active,
            balance=int(balance),
            total_earned=int(earned),
            last_active_at=user.last_active_at,
            created_at=user.created_at,
        )
        for user, balance, earned in rows
    ]
    return AdminUserListPage(items=items, next_cursor=next_cursor)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(
    user_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminUserDetail:
    user = _get_user_or_404(db, user_id)
    return _detail(db, user)


@router.get("/users/{user_id}/ledger", response_model=LedgerPage)
def get_user_ledger(
    user_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> LedgerPage:
    _get_user_or_404(db, user_id)
    return ledger_page(db, user_id, cursor=cursor, limit=limit)


@router.post("/users/{user_id}/credit", response_model=AdminUserDetail)
def credit_user(
    user_id: uuid.UUID,
    body: AdjustIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminUserDetail:
    user = _get_user_or_404(db, user_id)
    ledger.add_entry(
        db,
        user_id=user.id,
        amount=body.points,
        type=LedgerType.ADMIN_CREDIT,
        admin_id=admin.id,
        note=body.note,
    )
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="credit",
        entity_type="user",
        entity_id=user.id,
        metadata={"points": body.points, "note": body.note},
    )
    db.commit()
    return _detail(db, user)


@router.post("/users/{user_id}/debit", response_model=AdminUserDetail)
def debit_user(
    user_id: uuid.UUID,
    body: AdjustIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminUserDetail:
    user = _get_user_or_404(db, user_id)
    # Allow the balance to go negative (D3); flagged to admin via the ledger.
    ledger.add_entry(
        db,
        user_id=user.id,
        amount=-body.points,
        type=LedgerType.ADMIN_DEBIT,
        admin_id=admin.id,
        note=body.note,
    )
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="debit",
        entity_type="user",
        entity_id=user.id,
        metadata={"points": body.points, "note": body.note},
    )
    db.commit()
    return _detail(db, user)


@router.patch("/users/{user_id}", response_model=AdminUserDetail)
def set_user_status(
    user_id: uuid.UUID,
    body: UserStatusIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminUserDetail:
    user = _get_user_or_404(db, user_id)
    user.is_active = body.is_active
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="update_user",
        entity_type="user",
        entity_id=user.id,
        metadata={"is_active": body.is_active},
    )
    db.commit()
    db.refresh(user)
    return _detail(db, user)
