import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.errors import AppError

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


def hash_secret(secret: str) -> str:
    return _hasher.hash(secret)


def verify_secret(hashed: str, secret: str) -> bool:
    try:
        return _hasher.verify(hashed, secret)
    except VerifyMismatchError:
        return False


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(sub: str, aud: str = "broker", extra: dict[str, Any] | None = None) -> str:
    now = _now()
    payload = {
        "sub": sub,
        "aud": aud,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
        "jti": str(uuid.uuid4()),
    }
    # Dealer tokens carry dealer_id so the app can render the shop name without
    # a second round trip. Never trusted for authorisation — every request
    # re-reads the staff row and its dealership.
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def create_refresh_token(sub: str, aud: str = "broker") -> tuple[str, str]:
    now = _now()
    jti = str(uuid.uuid4())
    payload = {
        "sub": sub,
        "aud": aud,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_ttl_days),
        "jti": jti,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM), jti


def decode_token(token: str, *, expected_aud: str, expected_type: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[_ALGORITHM],
            audience=expected_aud,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.InvalidTokenError as exc:
        raise AppError("invalid_token", 401, "Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise AppError("invalid_token", 401, "Wrong token type")
    return payload


# Dealer-side call sites use these names; the worker side calls the same
# functions hash_secret/verify_secret. Aliases rather than a rename so no
# existing worker code has to change.
hash_password = hash_secret


def verify_password(password: str, password_hash: str) -> bool:
    return verify_secret(password_hash, password)
