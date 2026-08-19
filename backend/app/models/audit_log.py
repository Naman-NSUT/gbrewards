import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPkMixin


class AuditLog(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"

    actor_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    audit_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
