from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_redis
from app.core.errors import AppError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.auth import (
    LoginIn,
    RefreshIn,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _revoked_key(jti: str) -> str:
    return f"jwt:revoked:{jti}"


def _issue_pair(redis: Redis, user: User) -> TokenPair:
    access = create_access_token(sub=str(user.id))
    refresh, _ = create_refresh_token(sub=str(user.id))
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenPair)
def login(
    body: LoginIn,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenPair:
    """Direct credential login: upsert the broker by phone and issue tokens.

    No OTP — the phone number itself is the identity. Name and address are
    captured/refreshed on every login.
    """
    user = db.execute(select(User).where(User.phone == body.phone)).scalar_one_or_none()
    if user is None:
        user = User(phone=body.phone, name=body.name, address=body.address)
        db.add(user)
    else:
        if not user.is_active:
            raise AppError("account_disabled", 403, "This account has been disabled")
        user.name = body.name
        user.address = body.address

    user.is_verified = True
    db.commit()
    db.refresh(user)
    return _issue_pair(redis, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    body: RefreshIn,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenPair:
    payload = decode_token(body.refresh_token, expected_aud="broker", expected_type="refresh")
    jti = payload["jti"]
    if redis.exists(_revoked_key(jti)):
        raise AppError("invalid_token", 401, "Refresh token revoked")

    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise AppError("invalid_token", 401, "Unknown or disabled user")

    redis.set(_revoked_key(jti), "1", ex=settings.jwt_refresh_ttl_days * 86400)
    return _issue_pair(redis, user)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, redis: Redis = Depends(get_redis)) -> None:
    payload = decode_token(body.refresh_token, expected_aud="broker", expected_type="refresh")
    redis.set(_revoked_key(payload["jti"]), "1", ex=settings.jwt_refresh_ttl_days * 86400)
