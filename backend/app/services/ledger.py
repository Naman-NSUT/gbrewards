"""Single source of truth for point math (ledger hold model B).

available = balance - pending, where:
  balance = SUM(ledger_entries.amount) for the user
  pending = SUM(redemption_requests.points) for the user where status = 'pending'
"""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry
from app.models.redemption_request import RedemptionRequest


class LedgerType(StrEnum):
    SCAN_CREDIT = "scan_credit"
    RETURN_REVERSAL = "return_reversal"
    REDEMPTION_DEBIT = "redemption_debit"
    ADMIN_CREDIT = "admin_credit"
    ADMIN_DEBIT = "admin_debit"


def balance(session: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.user_id == user_id
    )
    return int(session.execute(stmt).scalar_one())


def pending(session: Session, user_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(RedemptionRequest.points), 0)).where(
        RedemptionRequest.user_id == user_id,
        RedemptionRequest.status == "pending",
    )
    return int(session.execute(stmt).scalar_one())


def available(session: Session, user_id: uuid.UUID) -> int:
    return balance(session, user_id) - pending(session, user_id)


def total_earned(session: Session, user_id: uuid.UUID) -> int:
    """Sum of all positive ledger movements (credits) for the user."""
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.user_id == user_id, LedgerEntry.amount > 0
    )
    return int(session.execute(stmt).scalar_one())


def add_entry(
    session: Session,
    *,
    user_id: uuid.UUID,
    amount: int,
    type: LedgerType,
    product_unit_id: uuid.UUID | None = None,
    redemption_id: uuid.UUID | None = None,
    admin_id: uuid.UUID | None = None,
    note: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LedgerEntry:
    """Append a ledger entry. Does NOT commit — the caller owns the transaction."""
    entry = LedgerEntry(
        user_id=user_id,
        amount=amount,
        type=str(type),
        product_unit_id=product_unit_id,
        redemption_id=redemption_id,
        admin_id=admin_id,
        note=note,
        entry_metadata=metadata,
    )
    session.add(entry)
    session.flush()
    return entry
