import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.admin import Admin
from app.models.redemption_request import RedemptionRequest
from app.models.user import User
from app.schemas.redemption import (
    RedemptionActionIn,
    RedemptionAdminOut,
    RedemptionUserBrief,
)
from app.services import redemption

router = APIRouter(prefix="/redemptions", tags=["admin-redemptions"])


def _to_admin_out(req: RedemptionRequest, user: User) -> RedemptionAdminOut:
    return RedemptionAdminOut(
        id=req.id,
        points=req.points,
        status=req.status,
        note=req.note,
        created_at=req.created_at,
        processed_at=req.processed_at,
        user=RedemptionUserBrief(id=user.id, phone=user.phone, name=user.name),
    )


@router.get("", response_model=list[RedemptionAdminOut])
def list_queue(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    status: str | None = None,
) -> list[RedemptionAdminOut]:
    stmt = select(RedemptionRequest, User).join(User, User.id == RedemptionRequest.user_id)
    if status is not None:
        stmt = stmt.where(RedemptionRequest.status == status)
    stmt = stmt.order_by(RedemptionRequest.created_at.desc())
    return [_to_admin_out(req, user) for req, user in db.execute(stmt).all()]


def _action_response(db: Session, req: RedemptionRequest) -> RedemptionAdminOut:
    db.commit()
    db.refresh(req)
    user = db.get(User, req.user_id)
    assert user is not None
    return _to_admin_out(req, user)


@router.post("/{redemption_id}/approve", response_model=RedemptionAdminOut)
def approve(
    redemption_id: uuid.UUID,
    body: RedemptionActionIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> RedemptionAdminOut:
    req = redemption.approve(db, redemption_id=redemption_id, admin=admin, note=body.note)
    return _action_response(db, req)


@router.post("/{redemption_id}/reject", response_model=RedemptionAdminOut)
def reject(
    redemption_id: uuid.UUID,
    body: RedemptionActionIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> RedemptionAdminOut:
    req = redemption.reject(db, redemption_id=redemption_id, admin=admin, note=body.note)
    return _action_response(db, req)


@router.post("/{redemption_id}/fulfill", response_model=RedemptionAdminOut)
def fulfill(
    redemption_id: uuid.UUID,
    body: RedemptionActionIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> RedemptionAdminOut:
    req = redemption.fulfill(db, redemption_id=redemption_id, admin=admin, note=body.note)
    return _action_response(db, req)
