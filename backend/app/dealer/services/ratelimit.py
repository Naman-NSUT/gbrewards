"""Fixed-window rate limiting.

Deliberately FAIL-CLOSED on the paying endpoint and FAIL-OPEN on lookups.

GB Rewards fails closed everywhere by accident — a Redis outage 500s the scan
endpoint. That is the right answer for an endpoint that pays money (better to
stop paying than to pay without limit) but the wrong answer for a read. Here the
choice is explicit per call site rather than an emergent property of where the
exception happens to land.
"""

from redis import Redis
from redis.exceptions import RedisError

from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


def enforce(
    redis: Redis,
    key: str,
    *,
    limit: int,
    window_s: int,
    fail_open: bool = False,
) -> None:
    full_key = f"rl:{key}"
    try:
        count = redis.incr(full_key)
        if count == 1:
            redis.expire(full_key, window_s)
    except RedisError as exc:
        if fail_open:
            logger.warning("ratelimit_unavailable_failing_open key=%s err=%s", key, exc)
            return
        logger.error("ratelimit_unavailable_failing_closed key=%s err=%s", key, exc)
        raise AppError(
            "rate_limit_unavailable",
            503,
            "Service is temporarily unavailable, please retry",
        ) from exc

    if count > limit:
        raise AppError("rate_limited", 429, "Too many requests, slow down")
