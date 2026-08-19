"""Warranty claims raised by customers from the public support site."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import TimestampMixin, UUIDPkMixin


class Claim(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "status in ('open','in_review','approved','rejected','closed')", name="status_valid"
        ),
        Index("ix_claims_status_created_at", "status", text("created_at DESC")),
        Index("ix_claims_warranty_id", "warranty_id"),
    )

    # Public-facing short reference the customer quotes on the phone. Generated,
    # not sequential, so it leaks no volume information.
    reference: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)

    warranty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warranties.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    issue_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'open'"))
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_admins.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
