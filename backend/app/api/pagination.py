"""Shared keyset (cursor) pagination for the append-only ledger."""

import base64
import binascii
import uuid
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.ledger_entry import LedgerEntry
from app.schemas.ledger import LedgerEntryOut, LedgerPage


def encode_cursor(created_at: datetime, entry_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{entry_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts, entry_id = raw.split("|", 1)
        return datetime.fromisoformat(ts), uuid.UUID(entry_id)
    except (binascii.Error, ValueError) as exc:
        raise AppError("validation_error", 400, "Invalid cursor") from exc


def ledger_page(db: Session, user_id: uuid.UUID, *, cursor: str | None, limit: int) -> LedgerPage:
    stmt = select(LedgerEntry).where(LedgerEntry.user_id == user_id)
    if cursor is not None:
        created_at, entry_id = decode_cursor(cursor)
        stmt = stmt.where(tuple_(LedgerEntry.created_at, LedgerEntry.id) < (created_at, entry_id))
    stmt = stmt.order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc()).limit(limit + 1)

    rows = list(db.execute(stmt).scalars().all())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.created_at, last.id)
        rows = rows[:limit]

    return LedgerPage(
        items=[LedgerEntryOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )
