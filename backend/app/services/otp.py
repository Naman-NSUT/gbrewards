"""Redis-backed OTP store + rate limiting (TECH_SPEC §3.1, §7.1)."""

import secrets

from redis import Redis

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_secret, verify_secret
from app.services.otp_provider import OtpProvider


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _attempts_key(phone: str) -> str:
    return f"otp:attempts:{phone}"


def _cooldown_key(phone: str) -> str:
    return f"otp:cooldown:{phone}"


def _daily_phone_key(phone: str) -> str:
    return f"otp:daily:phone:{phone}"


def _daily_ip_key(ip: str) -> str:
    return f"otp:daily:ip:{ip}"


def _incr_daily(redis: Redis, key: str, cap: int, error_code: str) -> None:
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, 86400)
    if count > cap:
        raise AppError(error_code, 429, "Daily OTP limit reached")


def issue_otp(redis: Redis, phone: str, ip: str, provider: OtpProvider) -> None:
    if redis.exists(_cooldown_key(phone)):
        raise AppError(
            "otp_cooldown",
            429,
            "Please wait before requesting another code",
            {"retry_after": settings.otp_resend_cooldown_seconds},
        )

    _incr_daily(redis, _daily_phone_key(phone), settings.otp_daily_cap_per_phone, "otp_daily_cap")
    _incr_daily(redis, _daily_ip_key(ip), settings.otp_daily_cap_per_ip, "otp_daily_cap")

    code = f"{secrets.randbelow(1_000_000):06d}"
    redis.set(_otp_key(phone), hash_secret(code), ex=settings.otp_ttl_seconds)
    redis.delete(_attempts_key(phone))
    redis.set(_cooldown_key(phone), "1", ex=settings.otp_resend_cooldown_seconds)

    provider.send(phone, code)


def verify_otp(redis: Redis, phone: str, code: str) -> None:
    """Raise AppError on any failure; return None on success (consumes the code)."""
    stored = redis.get(_otp_key(phone))
    if stored is None:
        raise AppError("otp_expired", 400, "Code expired or not requested")

    attempts = redis.incr(_attempts_key(phone))
    if attempts == 1:
        redis.expire(_attempts_key(phone), settings.otp_ttl_seconds)
    if attempts > settings.otp_max_attempts:
        redis.delete(_otp_key(phone))
        raise AppError("otp_too_many_attempts", 429, "Too many attempts")

    stored_hash = stored.decode() if isinstance(stored, bytes) else stored
    if not verify_secret(stored_hash, code):
        raise AppError("invalid_otp", 400, "Incorrect code")

    redis.delete(_otp_key(phone))
    redis.delete(_attempts_key(phone))
    redis.delete(_cooldown_key(phone))
