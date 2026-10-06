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
from app.models.mixins import TimestampMixin, UUIDPkMixin


class RedemptionRequest(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "redemption_requests"
    __table_args__ = (
        CheckConstraint("points > 0", name="points_positive"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_redemption_requests_status", "status"),
        Index(
            "ix_redemption_requests_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    # How many of the reward was asked for. ``points`` is still the amount that
    # gets debited; this is what the admin fulfilling the request hands over.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'pending'"))
    processed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reward_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rewards.id"), nullable=True
    )
