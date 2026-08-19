import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.audit_log import DealerAuditLog as AuditLog

# Actions where "why" is not optional. Anything that moves points or rewrites a
# customer's record has to be explicable to the client months later.
REASON_REQUIRED = {
    "void_warranty",
    "adjust_points",
    "approve_backdate",
    "reject_backdate",
    "edit_customer",
    "revoke_allocation",
    "suspend_dealer",
    "reject_self_registration",
}


def record_audit(
    session: Session,
    *,
    action: str,
    entity_type: str,
    actor_type: str = "admin",
    actor_id: uuid.UUID | None = None,
    actor_label: str | None = None,
    entity_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Append an audit row. Does NOT commit — it rides the caller's transaction,
    so an audited action that rolls back leaves no misleading audit trail.
    """
    if action in REASON_REQUIRED and not (reason and reason.strip()):
        raise AppError("reason_required", 400, f"'{action}' requires a reason")

    log = AuditLog(
        # Both systems write here. actor_admin_id is kept populated for admin
        # actors so the worker panel's existing audit screen keeps working
        # unchanged against rows the dealer side wrote.
        actor_admin_id=actor_id if actor_type == "admin" else None,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=actor_label,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        audit_metadata=metadata,
        ip=ip,
    )
    session.add(log)
    session.flush()
    return log
