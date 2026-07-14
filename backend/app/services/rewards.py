"""Reward catalog CRUD with admin audit (mutations write audit, GET does not)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.admin import Admin
from app.models.redemption_request import RedemptionRequest
from app.models.reward import Reward
from app.schemas.admin import RewardIn, RewardUpdateIn
from app.services.audit import record_audit


def list_rewards(db: Session) -> list[Reward]:
    return list(
        db.execute(
            select(Reward).order_by(Reward.sort_order, Reward.created_at)
        ).scalars()
    )


def _get_or_404(db: Session, reward_id: uuid.UUID) -> Reward:
    reward = db.get(Reward, reward_id)
    if reward is None:
        raise AppError("reward_not_found", 404, "Unknown reward")
    return reward


def create_reward(db: Session, *, admin: Admin, body: RewardIn) -> Reward:
    reward = Reward(
        title=body.title,
        description=body.description,
        points_cost=body.points_cost,
        image_url=body.image_url,
        is_active=body.is_active,
        sort_order=body.sort_order,
    )
    db.add(reward)
    db.flush()
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="create_reward",
        entity_type="reward",
        entity_id=reward.id,
        metadata={
            "title": reward.title,
            "points_cost": reward.points_cost,
            "is_active": reward.is_active,
            "sort_order": reward.sort_order,
        },
    )
    return reward


def update_reward(
    db: Session, *, admin: Admin, reward_id: uuid.UUID, body: RewardUpdateIn
) -> Reward:
    reward = _get_or_404(db, reward_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(reward, field, value)
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="update_reward",
        entity_type="reward",
        entity_id=reward.id,
        metadata={"changes": changes},
    )
    return reward


def delete_reward(db: Session, *, admin: Admin, reward_id: uuid.UUID) -> None:
    reward = _get_or_404(db, reward_id)
    referenced = db.execute(
        select(func.count())
        .select_from(RedemptionRequest)
        .where(RedemptionRequest.reward_id == reward_id)
    ).scalar_one()
    if referenced:
        raise AppError(
            "reward_in_use",
            409,
            "Reward referenced by redemptions",
            {"redemptions": int(referenced)},
        )
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="delete_reward",
        entity_type="reward",
        entity_id=reward.id,
        metadata={"title": reward.title},
    )
    db.delete(reward)
