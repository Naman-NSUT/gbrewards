"""Redemption requests with availability holds (TECH_SPEC §8, hold model B).

A pending request is itself the hold: available = balance - sum(pending points).
No ledger entry is written until approval (redemption_debit). Rejection/cancel
simply leave pending state, releasing the hold.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.admin import Admin
from app.models.redemption_request import RedemptionRequest
from app.models.user import User
from app.services import ledger
from app.services.audit import record_audit
from app.services.ledger import LedgerType


def _now() -> datetime:
    return datetime.now(UTC)


def create(db: Session, *, user: User, points: int) -> RedemptionRequest:
    # Serialize a user's redemption creates so concurrent requests can't
    # over-commit the same available balance (the redemption analogue of the
    # atomic claim's guard).
    db.execute(select(User.id).where(User.id == user.id).with_for_update())

    if points > ledger.available(db, user.id):
        raise AppError("insufficient_balance", 400, "Requested points exceed available balance")

    req = RedemptionRequest(user_id=user.id, points=points, status="pending")
    db.add(req)
    db.flush()
    return req


def _require_status(req: RedemptionRequest, expected: str) -> None:
    if req.status != expected:
        raise AppError(
            "invalid_state",
            409,
            f"Request is {req.status}, expected {expected}",
            {"status": req.status},
        )


def _lock(db: Session, redemption_id: uuid.UUID) -> RedemptionRequest:
    req = db.execute(
        select(RedemptionRequest).where(RedemptionRequest.id == redemption_id).with_for_update()
    ).scalar_one_or_none()
    if req is None:
        raise AppError("redemption_not_found", 404, "Unknown redemption request")
    return req


def approve(
    db: Session, *, redemption_id: uuid.UUID, admin: Admin, note: str | None
) -> RedemptionRequest:
    req = _lock(db, redemption_id)
    _require_status(req, "pending")
    ledger.add_entry(
        db,
        user_id=req.user_id,
        amount=-req.points,
        type=LedgerType.REDEMPTION_DEBIT,
        redemption_id=req.id,
        admin_id=admin.id,
        note=note,
    )
    req.status = "approved"
    req.processed_by_admin_id = admin.id
    req.processed_at = _now()
    req.note = note
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="approve_redemption",
        entity_type="redemption",
        entity_id=req.id,
        metadata={"points": req.points},
    )
    return req


def reject(
    db: Session, *, redemption_id: uuid.UUID, admin: Admin, note: str | None
) -> RedemptionRequest:
    req = _lock(db, redemption_id)
    _require_status(req, "pending")
    # No ledger entry — leaving 'pending' releases the hold.
    req.status = "rejected"
    req.processed_by_admin_id = admin.id
    req.processed_at = _now()
    req.note = note
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="reject_redemption",
        entity_type="redemption",
        entity_id=req.id,
        metadata={"points": req.points},
    )
    return req


def fulfill(
    db: Session, *, redemption_id: uuid.UUID, admin: Admin, note: str | None
) -> RedemptionRequest:
    req = _lock(db, redemption_id)
    _require_status(req, "approved")
    req.status = "fulfilled"
    req.processed_by_admin_id = admin.id
    req.processed_at = _now()
    if note is not None:
        req.note = note
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="fulfill_redemption",
        entity_type="redemption",
        entity_id=req.id,
        metadata={"points": req.points},
    )
    return req


def cancel(db: Session, *, redemption_id: uuid.UUID, user: User) -> RedemptionRequest:
    req = _lock(db, redemption_id)
    if req.user_id != user.id:
        raise AppError("redemption_not_found", 404, "Unknown redemption request")
    _require_status(req, "pending")
    req.status = "cancelled"
    req.processed_at = _now()
    return req
