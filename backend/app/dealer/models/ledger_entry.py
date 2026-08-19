"""Append-only point movements. Never UPDATEd, never DELETEd.

Balances are derived (SUM over this table), so there is no denormalised counter
that can drift from its own history. Voiding a registration writes a compensating
debit; it never edits or removes the original credit.

Two DB-level guards live in the migration rather than here in comments:
  * a partial unique index on (warranty_id) for registration credits, so a retried
    submission physically cannot produce a second credit even if the service layer
    is wrong;
  * a partial unique index on (redemption_id) for redemption debits, likewise.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import CreatedAtMixin, UUIDPkMixin

# Positive = credit to the dealer, negative = debit. Signedness lives in `amount`
# so a SUM is the balance with no per-type interpretation.
ENTRY_TYPES = (
    "registration_credit",
    "registration_reversal",
    "redemption_debit",
    "redemption_release",
    "admin_credit",
    "admin_debit",
)


class LedgerEntry(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "dealer_ledger_entries"
    __table_args__ = (
        Index(
            "ix_dealer_ledger_entries_dealer_id_created_at",
            "dealer_id",
            text("created_at DESC"),
        ),
        Index("ix_dealer_ledger_entries_type", "type"),
        Index("ix_dealer_ledger_entries_warranty_id", "warranty_id"),
    )

    # Points accrue to the DEALERSHIP, not the person who scanned. The staff
    # member is recorded for attribution, but the balance and the redemption are
    # the business's.
    dealer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id"), nullable=False
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_staff.id"), nullable=True
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)

    # The cause. Exactly one of these is set for machine-generated entries;
    # admin adjustments have neither and carry a mandatory `reason` instead.
    warranty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warranties.id"), nullable=True
    )
    redemption_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_redemptions.id"), nullable=True
    )

    # Which rate version produced this amount. Without it, a ledger row from
    # before a rate change is unexplainable after one — "why is this 50 when
    # registrations are worth 75?" has to have an answer six months later.
    rate_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_point_rates.id"), nullable=True
    )

    # Who caused it. Admin adjustments REQUIRE a reason — enforced in the service
    # and by a CHECK in the migration.
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealer_admins.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
