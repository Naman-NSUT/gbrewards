from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import redis as redis_lib
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.admin import Admin
from app.models.user import User

_redis_pool = redis_lib.ConnectionPool.from_url(settings.redis_url, decode_responses=True)

bearer_scheme = HTTPBearer(auto_error=False)

# Don't write last_active_at on every request — only if it's this stale.
_ACTIVITY_THROTTLE = timedelta(seconds=60)


def _touch_last_active(db: Session, user: User) -> None:
    now = datetime.now(UTC)
    if user.last_active_at is None or (now - user.last_active_at) > _ACTIVITY_THROTTLE:
        user.last_active_at = now
        db.commit()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> redis_lib.Redis:
    return redis_lib.Redis(connection_pool=_redis_pool)


def get_current_user(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if creds is None:
        raise AppError("invalid_token", 401, "Missing bearer token")
    payload = decode_token(creds.credentials, expected_aud="broker", expected_type="access")
    user = db.get(User, payload["sub"])
    if user is None:
        raise AppError("invalid_token", 401, "Unknown user")
    if not user.is_active:
        raise AppError("user_disabled", 403, "User is disabled")
    _touch_last_active(db, user)
    return user


def get_current_admin(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Admin:
    if creds is None:
        raise AppError("invalid_token", 401, "Missing bearer token")
    payload = decode_token(creds.credentials, expected_aud="admin", expected_type="access")
    admin = db.get(Admin, payload["sub"])
    if admin is None:
        raise AppError("invalid_token", 401, "Unknown admin")
    if not admin.is_active:
        raise AppError("admin_disabled", 403, "Admin is disabled")
    return admin
