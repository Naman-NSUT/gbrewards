"""Idempotency keys for dealer submissions.

The dealer is on a shop-floor connection, the app queues submissions offline, and
a human is double-tapping a button. A retry must return the ORIGINAL result, not
create a second warranty or a second credit.

Why a table and not just Redis: the guarantee has to survive a Redis restart,
because the thing it protects is money. Redis is a cache here, not the record.

`request_hash` catches the nastier case — the same key replayed with a DIFFERENT
body, which means a client bug rather than a retry, and must be rejected loudly
rather than silently returning someone else's result.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import CreatedAtMixin


class IdempotencyKey(CreatedAtMixin, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        CheckConstraint("status in ('in_progress','completed')", name="status_valid"),
        Index("ix_idempotency_keys_created_at", text("created_at DESC")),
    )

    # Client-supplied, scoped per dealer so two dealers cannot collide.
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    dealer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id"), primary_key=True
    )

    endpoint: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'in_progress'")
    )
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
