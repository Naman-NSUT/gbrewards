"""Dealers are business entities; staff are the humans who log in beneath one.

Two levels, not one. The compliance metric the client opens every morning is
per-dealership ("this shop was allocated 40 units and registered 6"), while
attribution for abuse investigation has to be per-person ("all 34 of the
suspicious registrations came from one phone"). A single login per shop cannot
express the second, and merging the two loses the first.

A shop that genuinely has one operator simply has one staff row, so this model
collapses to the simple case at no cost.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.dealer.models.mixins import TimestampMixin, UUIDPkMixin


class Dealer(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "dealers"
    __table_args__ = (
        CheckConstraint("status in ('active','suspended','closed')", name="status_valid"),
        Index("ix_dealers_status", "status"),
    )

    # Human-facing dealer code the client already uses on paperwork. Unique so
    # allocation CSV uploads can key on it rather than on a UUID nobody knows.
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))

    staff: Mapped[list["DealerStaff"]] = relationship(back_populates="dealer")


class DealerStaff(UUIDPkMixin, TimestampMixin, Base):
    """A person who can log in on behalf of a dealer.

    Staff are provisioned by an admin, never self-registered. Dealers are a known,
    finite set of business partners the client already has contracts with — there
    is no reason to let an arbitrary phone number create an account, and every
    reason not to when each registration pays points.
    """

    __tablename__ = "dealer_staff"
    __table_args__ = (
        CheckConstraint("role in ('owner','staff')", name="role_valid"),
        Index("ix_dealer_staff_dealer_id", "dealer_id"),
    )

    dealer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'staff'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dealer: Mapped[Dealer] = relationship(back_populates="staff")
