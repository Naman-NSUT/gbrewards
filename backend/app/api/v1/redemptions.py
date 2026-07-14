import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError
from app.models.redemption_request import RedemptionRequest
from app.models.user import User
from app.schemas.redemption import RedemptionCreateIn, RedemptionOut
from app.services import redemption

router = APIRouter(tags=["redemptions"])


@router.post("/redemptions", response_model=RedemptionOut, status_code=201)
def create_redemption(
    body: RedemptionCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedemptionRequest:
    # Exactly one of points / reward_id must be supplied.
    if (body.points is None) == (body.reward_id is None):
        raise AppError("validation_error", 422, "Provide either points or reward_id")
    if body.reward_id is not None:
        req = redemption.create_for_reward(db, user=user, reward_id=body.reward_id)
    else:
        assert body.points is not None
        req = redemption.create(db, user=user, points=body.points)
    db.commit()
    db.refresh(req)
    return req


@router.get("/redemptions", response_model=list[RedemptionOut])
def list_redemptions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RedemptionRequest]:
    return list(
        db.execute(
            select(RedemptionRequest)
            .where(RedemptionRequest.user_id == user.id)
            .order_by(RedemptionRequest.created_at.desc())
        ).scalars()
    )


@router.delete("/redemptions/{redemption_id}", response_model=RedemptionOut)
def cancel_redemption(
    redemption_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedemptionRequest:
    req = redemption.cancel(db, redemption_id=redemption_id, user=user)
    db.commit()
    db.refresh(req)
    return req
