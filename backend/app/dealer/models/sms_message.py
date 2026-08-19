"""Outbound SMS log.

GB Rewards sends OTPs fire-and-forget with no persisted record, which means
"did the customer actually get the message?" is unanswerable there. For this
system that question is the support desk's first question every time, so every
send is a row before it is an HTTP call, and the provider's response is written
back onto it.
"""

import uuid
from datetime import datetime
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.dealer.models.mixins import TimestampMixin, UUIDPkMixin


class SmsMessage(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sms_messages"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','sent','failed','delivered','undelivered')", name="status_valid"
        ),
        Index("ix_sms_messages_status_created_at", "status", text("created_at DESC")),
        Index("ix_sms_messages_to_phone", "to_phone"),
        Index("ix_sms_messages_warranty_id", "warranty_id"),
    )

    to_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    template_key: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # DLT template id actually used, recorded per message: when a template is
    # re-approved under a new id, historic rows still say which text went out.
    provider_template_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # The substituted variables, not the rendered body — enough to reconstruct the
    # message without storing PII twice.
    variables: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'queued'"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    warranty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warranties.id"), nullable=True
    )
