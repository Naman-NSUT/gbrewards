"""Idempotent submission handling.

The contract the dealer app relies on:

    A retry carrying the same Idempotency-Key returns the ORIGINAL result.
    It never creates a second warranty and never pays a second time.

Three cases, and all three matter on a shop-floor connection:

  * key unseen            → claim it, do the work, store the response
  * key seen + completed  → replay the stored response verbatim
  * key seen + in progress→ the first attempt is still running (or died
                            mid-flight). Return 409 `in_progress` so the client
                            retries in a moment rather than racing itself.

`request_hash` guards the case that silently corrupts data otherwise: the same
key replayed with a DIFFERENT body. That is not a retry, it is a client bug or an
attack, and returning the first result for the second request would attach one
customer's details to another's warranty. It is rejected loudly.

The record lives in Postgres, not Redis, because it protects money and must
survive a cache eviction. The unique PK does the actual work: two concurrent
requests with the same key cannot both claim it.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.idempotency import IdempotencyKey


def hash_request(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class Replay(Exception):
    """Raised to short-circuit with a previously stored response."""

    def __init__(self, status: int, body: dict[str, Any]) -> None:
        super().__init__("replayed")
        self.status = status
        self.body = body


def claim_key(
    session: Session,
    *,
    key: str,
    dealer_id: uuid.UUID,
    endpoint: str,
    payload: dict[str, Any],
) -> None:
    """Reserve the key for this request, or raise.

    Commits immediately and on purpose: the reservation must be visible to a
    concurrent duplicate even though the business transaction that follows has
    not finished. Without its own commit, two parallel double-taps both see an
    empty table and both proceed.
    """
    request_hash = hash_request(payload)

    existing = session.get(IdempotencyKey, {"key": key, "dealer_id": dealer_id})
    if existing is not None:
        _validate_and_replay(existing, request_hash)

    record = IdempotencyKey(
        key=key,
        dealer_id=dealer_id,
        endpoint=endpoint,
        request_hash=request_hash,
        status="in_progress",
    )
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        # Lost the race to a concurrent duplicate. Re-read and apply the same
        # rules — the winner may already have finished.
        session.rollback()
        existing = session.get(IdempotencyKey, {"key": key, "dealer_id": dealer_id})
        if existing is None:  # pragma: no cover - only on a genuine oddity
            raise
        _validate_and_replay(existing, request_hash)


def _validate_and_replay(record: IdempotencyKey, request_hash: str) -> None:
    if record.request_hash != request_hash:
        raise AppError(
            "idempotency_key_reused",
            409,
            "This idempotency key was already used with a different request",
        )
    if record.status == "completed" and record.response_body is not None:
        raise Replay(record.response_status or 200, record.response_body)
    raise AppError(
        "request_in_progress",
        409,
        "An identical request is still being processed; retry shortly",
    )


def complete_key(
    session: Session,
    *,
    key: str,
    dealer_id: uuid.UUID,
    status: int,
    body: dict[str, Any],
) -> None:
    """Store the response so a later retry can replay it."""
    record = session.get(IdempotencyKey, {"key": key, "dealer_id": dealer_id})
    if record is None:  # pragma: no cover - claim_key always creates it
        return
    record.status = "completed"
    record.response_status = status
    record.response_body = body
    record.completed_at = datetime.now(UTC)
    session.add(record)
    session.commit()


def release_key(session: Session, *, key: str, dealer_id: uuid.UUID) -> None:
    """Drop a reservation whose work failed, so the dealer can genuinely retry.

    Without this, a transient failure would wedge the key at `in_progress` and
    the dealer would be told "still processing" forever for a sale that never
    happened.
    """
    session.rollback()
    record = session.get(IdempotencyKey, {"key": key, "dealer_id": dealer_id})
    if record is not None and record.status != "completed":
        session.delete(record)
        session.commit()
