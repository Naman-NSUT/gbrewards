import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPkMixin


class LedgerEntry(UUIDPkMixin, CreatedAtMixin, Base):
    """Append-only point movements — the source of truth. Never UPDATE/DELETE."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index(
            "ix_ledger_entries_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
        Index("ix_ledger_entries_type", "type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    product_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_units.id"), nullable=True
    )
    redemption_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("redemption_requests.id"), nullable=True
    )
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Python attr renamed to avoid clashing with SQLAlchemy's reserved `.metadata`.
    entry_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
