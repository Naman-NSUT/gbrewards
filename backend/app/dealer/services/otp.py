"""Phone OTP for dealer staff.

Two deliberate differences from GB Rewards, both security-relevant.

1. GB Rewards' `/auth/otp/request` creates or UPDATES the user row — name,
   address, city, dob — and commits, BEFORE the code is verified. Anyone who
   knows a registered phone number can therefore overwrite that user's profile
   with no authentication at all, and can create unlimited unverified accounts.
   Here, nothing is written to the account on request. The OTP request only
   proves possession; it never mutates identity.

2. Dealer staff cannot self-register. The account must already exist, created by
   an admin. Dealers are contracted businesses, not walk-ups, and every
   registration pays points — an open sign-up on a paying system is an open till.
   An unknown number gets the same generic response as a known one, so the
   endpoint cannot be used to enumerate which numbers are dealers.
"""

import hashlib
import hmac
import secrets

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.dealer.services import sms

logger = get_logger(__name__)


def _code_key(phone: str) -> str:
    return f"otp:code:{phone}"


def _attempts_key(phone: str) -> str:
    return f"otp:attempts:{phone}"


def _cooldown_key(phone: str) -> str:
    return f"otp:cooldown:{phone}"


def _daily_key(phone: str) -> str:
    return f"otp:daily:{phone}"


def _hash(code: str) -> str:
    """Store a hash, not the code. A Redis dump should not be a list of live
    credentials."""
    return hashlib.sha256(f"{settings.jwt_secret}:{code}".encode()).hexdigest()


def issue(db: Session, redis: Redis, phone: str) -> None:
    if redis.exists(_cooldown_key(phone)):
        raise AppError("otp_cooldown", 429, "Please wait before requesting another code")

    daily = redis.incr(_daily_key(phone))
    if daily == 1:
        redis.expire(_daily_key(phone), 86400)
    if daily > settings.otp_daily_cap_per_phone:
        raise AppError("otp_daily_cap", 429, "Too many codes requested today")

    code = f"{secrets.randbelow(1_000_000):06d}"
    redis.set(_code_key(phone), _hash(code), ex=settings.otp_ttl_seconds)
    redis.delete(_attempts_key(phone))
    redis.set(_cooldown_key(phone), "1", ex=settings.otp_resend_cooldown_seconds)

    message = sms.queue(
        db,
        phone=phone,
        template_key="login_otp",
        variables={"otp": code, "minutes": str(settings.otp_ttl_seconds // 60)},
    )
    db.commit()
    sms.flush(db, message.id)


def verify(redis: Redis, phone: str, code: str) -> None:
    stored = redis.get(_code_key(phone))
    if stored is None:
        raise AppError("otp_expired", 400, "Code expired or not requested")

    attempts = redis.incr(_attempts_key(phone))
    if attempts == 1:
        redis.expire(_attempts_key(phone), settings.otp_ttl_seconds)
    if attempts > settings.otp_max_attempts:
        redis.delete(_code_key(phone))
        raise AppError("otp_attempts_exceeded", 429, "Too many incorrect attempts")

    # Constant-time compare: a timing oracle on a 6-digit code is a real
    # shortcut for an attacker who can retry.
    if not hmac.compare_digest(str(stored), _hash(code)):
        raise AppError("otp_invalid", 400, "Incorrect code")

    redis.delete(_code_key(phone), _attempts_key(phone))
