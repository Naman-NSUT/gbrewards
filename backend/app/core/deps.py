from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import redis as redis_lib
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.dealer.models.admin import DealerAdmin
from app.dealer.models.dealer import SIGNED_IN_STATUSES, Dealer, DealerStaff
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


# ---------------------------------------------------------------------------
# Dealer Rewards dependencies.
#
# The admins table is shared, so one back-office login works in both panels.
# Dealer staff are a separate identity (dealer_staff) with aud='dealer', so a
# worker token can never reach a dealer route and vice versa.
# ---------------------------------------------------------------------------

_DEALER_ACTIVITY_THROTTLE = timedelta(seconds=60)


def client_ip(request: Request) -> str:
    """Real client behind Render/Vercel's proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_current_staff(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> DealerStaff:
    if creds is None:
        raise AppError("invalid_token", 401, "Missing bearer token")
    payload = decode_token(creds.credentials, expected_aud="dealer", expected_type="access")
    staff = db.get(DealerStaff, payload["sub"])
    if staff is None:
        raise AppError("invalid_token", 401, "Unknown account")
    if not staff.is_active:
        raise AppError("account_disabled", 403, "This account has been disabled")

    # A suspended dealership must stop earning immediately, not when its staff
    # tokens happen to expire.
    dealer = db.get(Dealer, staff.dealer_id)
    # 'pending' shops are allowed through on purpose: a shop that just signed
    # itself up must be able to record sales straight away, because the warranty
    # record is the product. What it cannot do is redeem — see
    # services/redemption.py.
    if dealer is None or dealer.status not in SIGNED_IN_STATUSES:
        raise AppError("dealer_inactive", 403, "This dealership is not active")

    now = datetime.now(UTC)
    if staff.last_active_at is None or (now - staff.last_active_at) > _DEALER_ACTIVITY_THROTTLE:
        staff.last_active_at = now
        db.commit()
    return staff


def get_current_dealer_admin(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> DealerAdmin:
    """Back office for the DEALER programme.

    Its own table and its own token audience. A worker-panel admin token
    (aud='admin') is rejected here and vice versa, because the two programmes
    share no accounts — a person working on both holds two logins.
    """
    if creds is None:
        raise AppError("invalid_token", 401, "Missing bearer token")
    payload = decode_token(creds.credentials, expected_aud="dealer_admin", expected_type="access")
    admin = db.get(DealerAdmin, payload["sub"])
    if admin is None:
        raise AppError("invalid_token", 401, "Unknown admin")
    if not admin.is_active:
        raise AppError("admin_disabled", 403, "This account has been disabled")
    return admin


def require_admin_write(
    admin: DealerAdmin = Depends(get_current_dealer_admin),
) -> DealerAdmin:
    """Guard for anything that moves points or changes a warranty.

    'support' is read-mostly: it works the serial lookup and claims queue all day
    but must not be able to adjust a balance or approve a backdate.
    """
    if admin.role == "support":
        raise AppError("forbidden", 403, "This action needs more than a support account")
    return admin


def require_owner(admin: DealerAdmin = Depends(get_current_dealer_admin)) -> DealerAdmin:
    if admin.role != "owner":
        raise AppError("forbidden", 403, "This action requires an owner account")
    return admin


def idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    if idempotency_key is not None and len(idempotency_key) > 120:
        raise AppError("invalid_idempotency_key", 400, "Idempotency-Key is too long")
    return idempotency_key
