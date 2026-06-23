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
    verify_secret,
)
from app.models.admin import Admin
from app.schemas.admin import AdminLoginIn, AdminOut, AdminRefreshIn, AdminTokenPair

router = APIRouter(prefix="/auth", tags=["admin-auth"])


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
    if admin is None or not verify_secret(admin.password_hash, body.password):
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
