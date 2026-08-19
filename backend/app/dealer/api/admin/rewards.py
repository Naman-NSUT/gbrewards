"""Rewards catalogue and the redemption queue.

The catalogue is deliberately independent of the GB Rewards worker programme:
same schema shape, separate rows, separate prices. One shared catalogue would
mean a price edit silently repricing two programmes with different economics.

The money rule for redemptions: a PENDING request is itself the hold on the
balance (available = balance - pending). No ledger row exists until approval, so
rejecting releases the hold by ceasing to be pending, and there is no
compensating entry anyone can forget to write.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_dealer_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, count_of, pagination
from app.dealer.models.admin import DealerAdmin as Admin
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.reward import Redemption, Reward
from app.dealer.schemas.admin import (
    DealerBrief,
    Paginated,
    PointsSummaryOut,
    ReasonIn,
    RedemptionDecisionOut,
    RedemptionNoteIn,
    RedemptionOut,
    RewardIn,
    RewardOut,
    RewardUpdateIn,
    StaffBrief,
)
from app.dealer.schemas.common import Ok
from app.dealer.services import ledger
from app.dealer.services.audit import record_audit

router = APIRouter(tags=["admin-rewards"])


# --- Catalogue -------------------------------------------------------------


@router.get("/rewards", response_model=Paginated[RewardOut])
def list_rewards(
    is_active: bool | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[RewardOut]:
    stmt = select(Reward)
    if is_active is not None:
        stmt = stmt.where(Reward.is_active.is_(is_active))
    total = count_of(db, stmt)
    rewards = db.execute(
        stmt.order_by(Reward.sort_order.asc(), Reward.points_cost.asc())
        .limit(page.limit)
        .offset(page.offset)
    ).scalars()
    return Paginated[RewardOut](
        items=[RewardOut.model_validate(r) for r in rewards],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/rewards", response_model=RewardOut, status_code=201)
def create_reward(
    body: RewardIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Reward:
    reward = Reward(**body.model_dump())
    db.add(reward)
    db.flush()
    record_audit(
        db,
        action="create_reward",
        entity_type="reward",
        entity_id=reward.id,
        actor_id=admin.id,
        ip=client_ip(request),
        metadata={"name": reward.name, "points_cost": reward.points_cost},
    )
    db.commit()
    return reward


@router.get("/rewards/{reward_id}", response_model=RewardOut)
def get_reward(
    reward_id: uuid.UUID,
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Reward:
    return _get_reward(db, reward_id)


@router.patch("/rewards/{reward_id}", response_model=RewardOut)
def update_reward(
    reward_id: uuid.UUID,
    body: RewardUpdateIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Reward:
    reward = _get_reward(db, reward_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise AppError("nothing_to_update", 400, "No fields supplied")

    before = {field: getattr(reward, field) for field in changes}
    for field, value in changes.items():
        setattr(reward, field, value)

    record_audit(
        db,
        action="update_reward",
        entity_type="reward",
        entity_id=reward.id,
        actor_id=admin.id,
        ip=client_ip(request),
        # Price changes are the ones anyone asks about later; pending
        # redemptions froze their own cost at request time and are unaffected.
        metadata={"before": before, "after": changes},
    )
    db.commit()
    return reward


@router.delete("/rewards/{reward_id}", response_model=Ok)
def deactivate_reward(
    reward_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> Ok:
    """Soft delete. Redemptions reference the reward, so the row must survive."""
    reward = _get_reward(db, reward_id)
    if reward.is_active:
        reward.is_active = False
        record_audit(
            db,
            action="deactivate_reward",
            entity_type="reward",
            entity_id=reward.id,
            actor_id=admin.id,
            ip=client_ip(request),
            metadata={"name": reward.name},
        )
        db.commit()
    return Ok()


def _get_reward(db: Session, reward_id: uuid.UUID) -> Reward:
    reward = db.get(Reward, reward_id)
    if reward is None:
        raise AppError("reward_not_found", 404, "No such reward")
    return reward


# --- Redemption queue ------------------------------------------------------


def _redemption_select() -> Select[tuple[Redemption, Dealer, DealerStaff]]:
    return (
        select(Redemption, Dealer, DealerStaff)
        .join(Dealer, Dealer.id == Redemption.dealer_id)
        .outerjoin(DealerStaff, DealerStaff.id == Redemption.requested_by_staff_id)
    )


def _out(redemption: Redemption, dealer: Dealer, staff: DealerStaff | None) -> RedemptionOut:
    return RedemptionOut(
        id=redemption.id,
        dealer=DealerBrief(
            id=dealer.id,
            code=dealer.code,
            name=dealer.name,
            status=dealer.status,
            city=dealer.city,
        ),
        requested_by=(
            StaffBrief(id=staff.id, name=staff.name, phone=staff.phone, role=staff.role)
            if staff
            else None
        ),
        reward_id=redemption.reward_id,
        reward_name=redemption.reward_name,
        points=redemption.points,
        status=redemption.status,
        note=redemption.note,
        processed_by_admin_id=redemption.processed_by_admin_id,
        processed_at=redemption.processed_at,
        created_at=redemption.created_at,
    )


@router.get("/redemptions", response_model=Paginated[RedemptionOut])
def list_redemptions(
    status: str | None = Query(
        default=None, pattern="^(pending|approved|rejected|fulfilled|cancelled)$"
    ),
    dealer_id: uuid.UUID | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[RedemptionOut]:
    stmt = _redemption_select()
    if status:
        stmt = stmt.where(Redemption.status == status)
    if dealer_id:
        stmt = stmt.where(Redemption.dealer_id == dealer_id)

    total = count_of(db, stmt)
    rows = db.execute(
        # Oldest first within the queue: a dealer waiting three weeks for a
        # decision stops trusting the programme.
        stmt.order_by(Redemption.created_at.asc()).limit(page.limit).offset(page.offset)
    ).all()
    return Paginated[RedemptionOut](
        items=[_out(r, d, s) for r, d, s in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


def _load_for_decision(db: Session, redemption_id: uuid.UUID) -> tuple[Redemption, Dealer]:
    redemption = db.get(Redemption, redemption_id)
    if redemption is None:
        raise AppError("redemption_not_found", 404, "No such redemption")
    # Lock the DEALER row, not the redemption: it serialises every point-moving
    # decision for this dealer, so two admins approving two different requests
    # at the same moment cannot both pass the balance check.
    dealer = db.execute(
        select(Dealer).where(Dealer.id == redemption.dealer_id).with_for_update()
    ).scalar_one()
    return redemption, dealer


def _summary(db: Session, dealer_id: uuid.UUID) -> PointsSummaryOut:
    return PointsSummaryOut(
        balance=ledger.balance(db, dealer_id),
        pending=ledger.pending(db, dealer_id),
        available=ledger.available(db, dealer_id),
        total_earned=ledger.total_earned(db, dealer_id),
    )


@router.post("/redemptions/{redemption_id}/approve", response_model=RedemptionDecisionOut)
def approve_redemption(
    redemption_id: uuid.UUID,
    body: RedemptionNoteIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> RedemptionDecisionOut:
    """Approve and debit, in one transaction.

    The balance is re-checked HERE and not trusted from request time: points may
    have been clawed back by a void since the dealer asked, and approving into a
    balance that no longer exists would create points from nothing.

    The check is against the BALANCE, not against available. Other pending
    requests are requests, not commitments — a dealer with 70 points who asked
    for two 60-point rewards must be able to have one approved, and counting the
    other hold would deadlock the queue until an admin rejected something. The
    second approval then fails honestly on the balance the first one left.
    """
    redemption, dealer = _load_for_decision(db, redemption_id)
    if redemption.status != "pending":
        raise AppError("not_pending", 409, f"This redemption is already '{redemption.status}'")

    balance = ledger.balance(db, dealer.id)
    if balance < redemption.points:
        raise AppError(
            "insufficient_points",
            409,
            "This dealer no longer has enough points for this reward",
            {
                "balance": balance,
                "other_pending_holds": ledger.pending(db, dealer.id) - redemption.points,
                "required": redemption.points,
            },
        )

    reward = db.get(Reward, redemption.reward_id) if redemption.reward_id else None
    if reward is not None and reward.stock is not None:
        if reward.stock <= 0:
            raise AppError("out_of_stock", 409, f"'{reward.name}' is out of stock")
        # Decremented on APPROVAL, never on request: a queue of requests must not
        # be able to reserve away stock that is never actually issued.
        reward.stock -= 1

    redemption.status = "approved"
    redemption.processed_by_admin_id = admin.id
    redemption.processed_at = datetime.now(UTC)
    if body.note:
        redemption.note = body.note

    ledger.add_entry(
        db,
        dealer_id=dealer.id,
        staff_id=redemption.requested_by_staff_id,
        amount=-redemption.points,
        type=ledger.REDEMPTION_DEBIT,
        redemption_id=redemption.id,
        admin_id=admin.id,
        reason=body.note,
        metadata={"reward": redemption.reward_name},
    )
    record_audit(
        db,
        action="approve_redemption",
        entity_type="redemption",
        entity_id=redemption.id,
        actor_id=admin.id,
        reason=body.note,
        ip=client_ip(request),
        metadata={
            "dealer_id": str(dealer.id),
            "points": redemption.points,
            "reward": redemption.reward_name,
        },
    )
    db.commit()

    staff = (
        db.get(DealerStaff, redemption.requested_by_staff_id)
        if redemption.requested_by_staff_id
        else None
    )
    return RedemptionDecisionOut(
        redemption=_out(redemption, dealer, staff), points=_summary(db, dealer.id)
    )


@router.post("/redemptions/{redemption_id}/reject", response_model=RedemptionDecisionOut)
def reject_redemption(
    redemption_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> RedemptionDecisionOut:
    """Reject a request. No ledger entry, by design.

    The pending row WAS the hold; ceasing to be pending releases it. Writing a
    'release' entry would be a second bookkeeping path for the same fact, and
    the two would eventually disagree.
    """
    redemption, dealer = _load_for_decision(db, redemption_id)
    if redemption.status != "pending":
        raise AppError("not_pending", 409, f"This redemption is already '{redemption.status}'")

    redemption.status = "rejected"
    redemption.note = body.reason
    redemption.processed_by_admin_id = admin.id
    redemption.processed_at = datetime.now(UTC)

    record_audit(
        db,
        action="reject_redemption",
        entity_type="redemption",
        entity_id=redemption.id,
        actor_id=admin.id,
        reason=body.reason,
        ip=client_ip(request),
        metadata={"dealer_id": str(dealer.id), "points": redemption.points},
    )
    db.commit()

    staff = (
        db.get(DealerStaff, redemption.requested_by_staff_id)
        if redemption.requested_by_staff_id
        else None
    )
    return RedemptionDecisionOut(
        redemption=_out(redemption, dealer, staff), points=_summary(db, dealer.id)
    )


@router.post("/redemptions/{redemption_id}/mark-fulfilled", response_model=RedemptionDecisionOut)
def mark_fulfilled(
    redemption_id: uuid.UUID,
    body: RedemptionNoteIn,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> RedemptionDecisionOut:
    """The reward physically went out. Points were already debited on approval."""
    redemption, dealer = _load_for_decision(db, redemption_id)
    if redemption.status != "approved":
        raise AppError(
            "not_approved",
            409,
            "Only an approved redemption can be marked fulfilled",
            {"status": redemption.status},
        )

    redemption.status = "fulfilled"
    if body.note:
        # Where the courier docket number goes.
        redemption.note = body.note

    record_audit(
        db,
        action="fulfil_redemption",
        entity_type="redemption",
        entity_id=redemption.id,
        actor_id=admin.id,
        reason=body.note,
        ip=client_ip(request),
        metadata={"dealer_id": str(dealer.id), "points": redemption.points},
    )
    db.commit()

    staff = (
        db.get(DealerStaff, redemption.requested_by_staff_id)
        if redemption.requested_by_staff_id
        else None
    )
    return RedemptionDecisionOut(
        redemption=_out(redemption, dealer, staff), points=_summary(db, dealer.id)
    )
