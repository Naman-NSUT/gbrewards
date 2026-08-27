import secrets

from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_redis
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_secret,
    verify_secret,
)
from app.models.admin import Admin
from app.schemas.admin import AdminLoginIn, AdminOut, AdminRefreshIn, AdminTokenPair

router = APIRouter(prefix="/auth", tags=["admin-auth"])

# Something to verify against when the email is unknown, so that answer costs the
# same as a real one. Argon2 is ~50-100ms by design; a row that is not there costs
# a database round trip and nothing else, so `admin is None or not verify_secret(...)`
# short-circuits and replies in ~1ms. That gap is an order of magnitude wider than
# network jitter, which turns this endpoint into a directory of the client's
# back-office staff: type an address, time the 401, learn whether the person works
# here. Nothing else rate limits this route, so the list is free to collect.
#
# Hashed ONCE, at import. Generating a throwaway hash per miss would pay argon2 on
# the miss path too, but hashing is slower than verifying — the gap would reopen
# pointing the other way, and unknown emails would become the slow ones.
_DUMMY_PASSWORD_HASH = hash_secret(secrets.token_urlsafe(32))


def _revoked_key(jti: str) -> str:
    return f"jwt:revoked:{jti}"


def _issue_pair(admin: Admin) -> AdminTokenPair:
    access = create_access_token(sub=str(admin.id), aud="admin")
    refresh, _ = create_refresh_token(sub=str(admin.id), aud="admin")
    return AdminTokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
        admin=AdminOut.model_validate(admin),
    )


@router.post("/login", response_model=AdminTokenPair)
def login(body: AdminLoginIn, db: Session = Depends(get_db)) -> AdminTokenPair:
    admin = db.execute(select(Admin).where(Admin.email == body.email)).scalar_one_or_none()
    # Unconditional, and before the `admin is None` test: an unknown email must do
    # the same argon2 work as a known one. See _DUMMY_PASSWORD_HASH.
    password_ok = verify_secret(
        admin.password_hash if admin is not None else _DUMMY_PASSWORD_HASH,
        body.password,
    )
    if admin is None or not password_ok:
        raise AppError("invalid_credentials", 401, "Invalid email or password")
    if not admin.is_active:
        raise AppError("admin_disabled", 403, "Admin is disabled")
    return _issue_pair(admin)


@router.post("/refresh", response_model=AdminTokenPair)
def refresh(
    body: AdminRefreshIn,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminTokenPair:
    payload = decode_token(body.refresh_token, expected_aud="admin", expected_type="refresh")
    jti = payload["jti"]
    if redis.exists(_revoked_key(jti)):
        raise AppError("invalid_token", 401, "Refresh token revoked")

    admin = db.get(Admin, payload["sub"])
    if admin is None or not admin.is_active:
        raise AppError("invalid_token", 401, "Unknown or disabled admin")

    redis.set(_revoked_key(jti), "1", ex=settings.jwt_refresh_ttl_days * 86400)
    return _issue_pair(admin)
