"""Which serials a dealer is allowed to register.

This is the load-bearing anti-abuse control and the denominator of the compliance
metric. It is also what lets a sale complete when GB Rewards is unreachable: if a
serial is in this dealer's allocation, we already know the dealer is entitled to
register it, without asking anyone.

A serial may be allocated to at most one dealer at a time, enforced by a partial
unique index (see the migration) rather than by application logic — a
double-allocated serial is a double-payable registration.
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
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPkMixin


class AllocationBatch(UUIDPkMixin, CreatedAtMixin, Base):
    """One CSV upload. Kept so a bad upload can be traced and reversed wholesale."""

    __tablename__ = "allocation_batches"

    filename: Mapped[str | None] = mapped_column(String(400), nullable=True)
    uploaded_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_admins.id"), nullable=False
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ok_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Per-row rejections, so the admin sees exactly which lines failed and why
    # instead of a bare "23 rows failed".
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class Allocation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint(
            "status in ('allocated','registered','revoked','returned')", name="status_valid"
        ),
        Index("ix_allocations_dealer_id_status", "dealer_id", "status"),
        Index("ix_allocations_serial", "serial"),
        Index("ix_allocations_batch_id", "batch_id"),
    )

    serial: Mapped[str] = mapped_column(String(128), nullable=False)
    dealer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("allocation_batches.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'allocated'")
    )
    # Invoice/dispatch reference from the client's own despatch system, if any.
    dispatch_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
