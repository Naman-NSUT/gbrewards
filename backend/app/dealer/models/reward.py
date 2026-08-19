"""Rewards catalogue and redemption requests.

Deliberately independent of the GB Rewards worker catalogue. Dealers are a
different population with different economics: a registration is worth a
different amount than an assembly scan, the two point currencies are not
interchangeable, and a shared catalogue would mean one price edit silently
repricing two programmes at once. Same schema shape, separate rows.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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
from app.dealer.models.mixins import TimestampMixin, UUIDPkMixin


class Reward(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "dealer_rewards"
    __table_args__ = (CheckConstraint("points_cost > 0", name="points_cost_positive"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    # NULL = unlimited. Decremented only on approval, never on request.
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class Redemption(UUIDPkMixin, TimestampMixin, Base):
    """A pending request is itself the hold on the balance.

    available = balance - SUM(points of pending redemptions). No ledger row is
    written until approval, so a rejected request releases its hold by simply
    ceasing to be pending — there is no compensating entry to forget.
    """

    __tablename__ = "dealer_redemptions"
    __table_args__ = (
        CheckConstraint("points > 0", name="points_positive"),
        CheckConstraint(
            "status in ('pending','approved','rejected','fulfilled','cancelled')",
            name="status_valid",
        ),
        Index("ix_dealer_redemptions_dealer_id_created_at", "dealer_id", text("created_at DESC")),
        Index("ix_dealer_redemptions_status", "status"),
    )

    dealer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id"), nullable=False
    )
    requested_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_staff.id"), nullable=True
    )
    reward_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_rewards.id"), nullable=True
    )
    # Frozen at request time so a later catalogue edit cannot change the price of
    # a request already in the queue.
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
