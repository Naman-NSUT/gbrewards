"""Audit trail for the dealer programme only.

Separate from the worker programme's `audit_logs`. Nothing is shared between the
two systems, so "who changed this" is answered per programme.
"""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import CreatedAtMixin, UUIDPkMixin


class DealerAuditLog(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "dealer_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_type in ('admin','dealer_staff','customer','system')", name="actor_type_valid"
        ),
        Index("ix_dealer_audit_logs_created_at", text("created_at DESC")),
        Index("ix_dealer_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_dealer_audit_logs_actor_type_actor_id", "actor_type", "actor_id"),
    )

    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Free text for actors with no row of their own (a cron job, the sync task).
    actor_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_admins.id"), nullable=True
    )

    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
