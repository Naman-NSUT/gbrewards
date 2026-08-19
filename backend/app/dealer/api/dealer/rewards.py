"""The dealer's rewards screen.

Scoping is structural, not a check bolted on afterwards: every statement here
filters on the dealer_id carried by the caller's token, so there is no code path
that loads another dealership's redemption and then decides whether to show it.
A lookup that misses returns 404, not 403 — a staff member should not be able to
probe which redemption ids exist.

Points are the incentive, never the product. Nothing on this surface can create
points; it can only spend them, and spending needs an admin to approve. The one
endpoint that commits money is rate limited fail-closed and accepts an optional
Idempotency-Key, because a double-tapped "Redeem" is a real event on a shop
floor and it must not place two holds on one balance.
"""

import uuid

import redis as redis_lib
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_staff, get_db, get_redis, idempotency_key
from app.dealer.models.dealer import DealerStaff
from app.dealer.schemas.rewards import (
    CatalogueOut,
    RedeemIn,
    RedemptionOut,
    RedemptionPage,
    RewardOut,
)
from app.dealer.services import idempotency, ratelimit
from app.dealer.services import redemption as redemption_svc

router = APIRouter(tags=["dealer-rewards"])

# A dealership requesting more than this in an hour is not shopping, it is
# probing. Fail-closed like the registration limits: this endpoint commits
# points, so if we cannot count we do not accept.
_REDEMPTIONS_PER_HOUR = 20


@router.get("/rewards", response_model=CatalogueOut)
def list_rewards(
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> CatalogueOut:
    view = redemption_svc.catalogue(db, dealer_id=staff.dealer_id)
    return CatalogueOut(
        balance=view.balance,
        pending=view.pending,
        available=view.available,
        items=[
            RewardOut(
                id=entry.reward.id,
                name=entry.reward.name,
                description=entry.reward.description,
                points_cost=entry.reward.points_cost,
                image_url=entry.reward.image_url,
                in_stock=entry.in_stock,
                affordable=entry.affordable,
                short_by=entry.short_by,
            )
            for entry in view.entries
        ],
    )


@router.post("/redemptions", response_model=RedemptionOut, status_code=201)
def request_redemption(
    body: RedeemIn,
    response: Response,
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
    key: str | None = Depends(idempotency_key),
) -> RedemptionOut:
    ratelimit.enforce(
        redis, f"redeem:{staff.dealer_id}", limit=_REDEMPTIONS_PER_HOUR, window_s=3600
    )

    # Optional, unlike registrations: this screen is online-only and nothing is
    # queued offline, so demanding a key would be ceremony. When the app does
    # send one, a retry replays instead of placing a second hold.
    payload = body.model_dump(mode="json")
    if key:
        try:
            idempotency.claim_key(
                db,
                key=key,
                dealer_id=staff.dealer_id,
                endpoint="POST /dealer/redemptions",
                payload=payload,
            )
        except idempotency.Replay as replay:
            response.status_code = replay.status
            return RedemptionOut.model_validate(replay.body)

    try:
        redemption = redemption_svc.create(
            db, staff=staff, reward_id=body.reward_id, note=body.note
        )
        out = RedemptionOut.model_validate(redemption)
        db.commit()
    except Exception:
        if key:
            # Free the key so a genuine retry works, rather than wedging it at
            # "in progress" for a request that never happened.
            idempotency.release_key(db, key=key, dealer_id=staff.dealer_id)
        raise

    if key:
        idempotency.complete_key(
            db,
            key=key,
            dealer_id=staff.dealer_id,
            status=201,
            body=out.model_dump(mode="json"),
        )
    return out


@router.get("/redemptions", response_model=RedemptionPage)
def list_redemptions(
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> RedemptionPage:
    rows, total = redemption_svc.history(
        db, dealer_id=staff.dealer_id, status=status, limit=limit, offset=offset
    )
    return RedemptionPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[RedemptionOut.model_validate(row) for row in rows],
    )


@router.post("/redemptions/{redemption_id}/cancel", response_model=RedemptionOut)
def cancel_redemption(
    redemption_id: uuid.UUID,
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> RedemptionOut:
    redemption = redemption_svc.get_for_dealer(
        db, redemption_id=redemption_id, dealer_id=staff.dealer_id
    )
    redemption_svc.cancel(db, redemption=redemption, staff=staff)
    out = RedemptionOut.model_validate(redemption)
    db.commit()
    return out
