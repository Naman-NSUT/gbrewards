"""Audit trail for administrative actions (invariant: audit everything admin)."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit(
    session: Session,
    *,
    actor_admin_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an audit row. Does NOT commit — the caller owns the transaction."""
    entry = AuditLog(
        actor_admin_id=actor_admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        audit_metadata=metadata,
    )
    session.add(entry)
    session.flush()
    return entry
