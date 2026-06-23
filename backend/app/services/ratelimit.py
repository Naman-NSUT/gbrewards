"""Fixed-window rate limiting backed by Redis (anti-abuse)."""

from redis import Redis

from app.core.errors import AppError


def enforce_rate(redis: Redis, key: str, *, limit: int, window_s: int) -> None:
    """Allow `limit` hits per `window_s`. Raises rate_limited (429) when exceeded."""
    full_key = f"rl:{key}"
    count = redis.incr(full_key)
    if count == 1:
        redis.expire(full_key, window_s)
    if count > limit:
        raise AppError("rate_limited", 429, "Too many requests, slow down")
