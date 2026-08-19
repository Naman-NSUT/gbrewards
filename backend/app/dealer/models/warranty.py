"""The warranty record — the actual product of this system.

Status lifecycle, and why each state exists:

    pending_review ──approve──> active
        ^                          ^
        │                          │
   (customer self-registered,      │
    dealer never did)              │
                                   │
    pending_backdate ──approve─────┤
        ^                          │
        │                          │
   (dealer claimed an invoice      │
    date older than the grace      │
    window)                        │
                                   │
    pending_confirmation ──confirm─┤
        ^                          │
        │                          ├──claim raised──> claimed ──┐
   (only when REQUIRE_CUSTOMER_    │                            │
    CONFIRMATION is on)            │                            │
                                   └──void──────> voided <──────┘
                                                    ^
                                            (return, dispute,
                                             admin action)

`expired` is deliberately NOT a stored status. It is derived from
`warranty_end_date < today`, so no cron job mutates historic rows and no outage
leaves thousands of warranties in a wrong state. Storing it would buy nothing and
create a class of bug where the record's status disagrees with its own dates.

Everything that moves a warranty between states writes a WarrantyEvent. The
status column is a cache of the latest event; the events are the history.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.dealer.models.customer import Customer
from app.dealer.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPkMixin

# States in which a warranty occupies its serial. A serial may carry exactly one
# warranty in any of these states at a time — enforced by a partial unique index
# in the migration, not by application logic.
LIVE_STATUSES = (
    "pending_confirmation",
    "pending_review",
    "pending_backdate",
    "active",
    "claimed",
)
ALL_STATUSES = (*LIVE_STATUSES, "voided")


class Warranty(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "warranties"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending_confirmation','pending_review','pending_backdate',"
            "'active','claimed','voided')",
            name="status_valid",
        ),
        CheckConstraint(
            "source in ('dealer','customer_self','admin','migration')", name="source_valid"
        ),
        CheckConstraint("warranty_end_date >= warranty_start_date", name="dates_ordered"),
        CheckConstraint("warranty_months > 0", name="warranty_months_positive"),
        CheckConstraint("backdate_days >= 0", name="backdate_days_non_negative"),
        Index("ix_warranties_serial", "serial"),
        Index("ix_warranties_dealer_id_created_at", "dealer_id", text("created_at DESC")),
        Index("ix_warranties_customer_id", "customer_id"),
        Index("ix_warranties_status", "status"),
        Index("ix_warranties_warranty_end_date", "warranty_end_date"),
    )

    serial: Mapped[str] = mapped_column(String(128), nullable=False)

    # --- Product identity, FROZEN at registration ---------------------------
    # Copied from the unit at the moment of sale rather than joined at read time.
    # A future change to the model's warranty policy must not retroactively
    # rewrite a warranty that was already sold under the old terms.
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_units.id"), nullable=True
    )
    # Frozen at sale time alongside the model name: the rate that paid for this
    # registration was the product's rate, and the product must stay knowable
    # even if the unit row is later voided by manufacturing.
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_products.id"), nullable=True
    )
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warranty_months: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Who sold it --------------------------------------------------------
    dealer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id"), nullable=True
    )
    # Which human at the shop. Null for customer self-registrations.
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_staff.id"), nullable=True
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )

    invoice_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- The clock ----------------------------------------------------------
    # Server-authoritative. Never a value the dealer freely types: the dealer may
    # supply invoice_date, which can pull the start BACKWARD by at most
    # BACKDATE_GRACE_DAYS; anything further needs admin approval. warranty_end_date
    # is stored, not derived, for the freezing reason above.
    warranty_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    warranty_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # How many days the start was pulled back from the server date, and by whose
    # authority. Non-zero values are what the admin backdating report filters on.
    backdate_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    backdate_approved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_admins.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'dealer'"))

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Proof of purchase for customer self-registrations (object key, not bytes).
    proof_file_key: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # Set when the registration was accepted without the unit being verifiable
    # against GB Rewards (allocation-only, source unreachable). Surfaces on an
    # admin reconciliation queue instead of silently pretending we verified it.
    unit_unverified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    customer: Mapped["Customer"] = relationship("Customer", lazy="joined")


class WarrantyEvent(UUIDPkMixin, CreatedAtMixin, Base):
    """Append-only history of everything that happened to a warranty.

    Never updated, never deleted. The `status` column on Warranty is a
    denormalised cache of the most recent event here; if the two ever disagree,
    this table is right.
    """

    __tablename__ = "warranty_events"
    __table_args__ = (
        Index("ix_warranty_events_warranty_id_created_at", "warranty_id", text("created_at DESC")),
    )

    warranty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warranties.id"), nullable=False
    )
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
