"""Versioned points-per-registration, PER PRODUCT.

A registration is worth what the PRODUCT is worth, mirroring how worker scan
points already vary by product (products.points_value). The two are separate
numbers for separate populations: what a factory worker earns for assembling a
mattress and what a dealer earns for recording its sale are different economics
and must be tunable independently.

Exactly one rate is current per product: `effective_to IS NULL` marks it, and a
partial unique index on (product_id) makes "two current rates for one product"
unrepresentable.

The client has not decided what a registration is worth, and will change their
mind after launch. Rather than a config constant that silently rewrites the
meaning of history, each rate is a row with an effective window, and every ledger
entry points at the rate version that produced it.

Exactly one rate is current at a time: `effective_to IS NULL` marks it, and a
partial unique index in the migration makes "two current rates" unrepresentable.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import CreatedAtMixin, UUIDPkMixin


class PointRate(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "dealer_point_rates"
    __table_args__ = (
        CheckConstraint("points_per_registration >= 0", name="points_non_negative"),
        CheckConstraint(
            "effective_to is null or effective_to >= effective_from", name="window_ordered"
        ),
        Index("ix_dealer_point_rates_product_id", "product_id"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    points_per_registration: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    # NULL means "currently in force".
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True
    )
