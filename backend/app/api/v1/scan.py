import redis as redis_lib
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.scan import ProductBrief, ScanClaimIn, ScanClaimOut
from app.services.claim import claim
from app.services.ratelimit import enforce_rate

router = APIRouter(tags=["scan"])


@router.post("/scan/claim", response_model=ScanClaimOut)
def scan_claim(
    body: ScanClaimIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> ScanClaimOut:
    enforce_rate(redis, f"scan:{user.id}", limit=settings.scan_rate_per_min, window_s=60)
    result = claim(db, user_id=user.id, token=body.token)
    return ScanClaimOut(
        product=ProductBrief(
            id=result.product.id,
            name=result.product.name,
            points_value=result.product.points_value,
        ),
        points_awarded=result.points_awarded,
        balance=result.balance,
        available=result.available,
        claimed_at=result.claimed_at,
        idempotent=result.idempotent,
    )
