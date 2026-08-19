"""The dealer programme's own unit registry and QR batches.

This is a FULL registry, not a mirror: these tokens are generated here, printed
on their own label, and scanned by the dealer app. They are unrelated to the
worker programme's `product_units` — a mattress carries two QR labels, one per
programme, and the two serials have no link.

Consequence worth remembering when reading this code: nothing here can tell you
whether the factory ever assembled the unit. The dealer registry is authoritative
for the dealer programme and knows nothing else.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPkMixin


class DealerQrBatch(UUIDPkMixin, CreatedAtMixin, Base):
    """One print run. Kept so a batch can be traced, reprinted or voided whole."""

    __tablename__ = "dealer_qr_batches"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_admins.id"), nullable=True
    )


class DealerUnit(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "dealer_units"
    __table_args__ = (
        CheckConstraint("status in ('active','void')", name="status_valid"),
        Index("ix_dealer_units_product_id", "product_id"),
        Index("ix_dealer_units_batch_id", "batch_id"),
        Index("ix_dealer_units_status", "status"),
    )

    # The string encoded in the dealer QR and printed beneath it. Unguessable
    # (UUIDv4) because a guessable token is a registrable unit.
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_products.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_qr_batches.id"), nullable=True
    )
    # Only 'active' and 'void' here. Whether a unit has been SOLD is
    # warranties.status, not a column on the unit: one physical thing, one place
    # that says what happened to it.
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
