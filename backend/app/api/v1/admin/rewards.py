import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.models.admin import Admin
from app.models.reward import Reward
from app.schemas.admin import RewardIn, RewardOut, RewardUpdateIn
from app.services import rewards

router = APIRouter(tags=["admin-rewards"])


@router.get("/rewards", response_model=list[RewardOut])
def list_rewards(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[Reward]:
    return rewards.list_rewards(db)


@router.post("/rewards", response_model=RewardOut, status_code=201)
def create_reward(
    body: RewardIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Reward:
    reward = rewards.create_reward(db, admin=admin, body=body)
    db.commit()
    db.refresh(reward)
    return reward


@router.patch("/rewards/{reward_id}", response_model=RewardOut)
def update_reward(
    reward_id: uuid.UUID,
    body: RewardUpdateIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Reward:
    reward = rewards.update_reward(db, admin=admin, reward_id=reward_id, body=body)
    db.commit()
    db.refresh(reward)
    return reward


@router.delete("/rewards/{reward_id}", status_code=204)
def delete_reward(
    reward_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    rewards.delete_reward(db, admin=admin, reward_id=reward_id)
    db.commit()
