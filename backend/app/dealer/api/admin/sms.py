"""The SMS delivery log, and the retry the support desk needs.

GB Rewards sends fire-and-forget with nothing persisted, so 'did the customer
get the message?' is unanswerable there. Here every send is a row before it is
an HTTP call — this screen is that row, and the retry button is what makes a
failed message a recoverable event rather than a lost one.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_dealer_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, count_of, day_window, like, pagination
from app.dealer.models.admin import DealerAdmin as Admin
from app.dealer.models.sms_message import SmsMessage
from app.dealer.schemas.admin import Paginated, SmsOut
from app.dealer.services import sms as sms_svc
from app.dealer.services.audit import record_audit

router = APIRouter(tags=["admin-sms"])

RETRYABLE = ("failed", "queued", "undelivered")


def _preview(message: SmsMessage) -> str | None:
    """Render what was (or would be) sent, from the template and the variables.

    The body is not stored — the variables are — so this reconstructs it rather
    than duplicating the customer's name and phone into a second column.
    """
    template = sms_svc.TEMPLATES.get(message.template_key)
    if template is None:
        return None
    values = message.variables or {}
    return template.body.format(**{key: values.get(key, "") for key in template.variables})


def to_sms_out(message: SmsMessage) -> SmsOut:
    return SmsOut.model_validate(message).model_copy(update={"preview": _preview(message)})


@router.get("/sms", response_model=Paginated[SmsOut])
def list_messages(
    status: str | None = Query(
        default=None, pattern="^(queued|sent|failed|delivered|undelivered)$"
    ),
    phone: str | None = Query(default=None, max_length=20),
    template_key: str | None = Query(default=None, max_length=60),
    warranty_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=200, description="matches the error text"),
    date_from: date | None = None,
    date_to: date | None = None,
    page: Pagination = Depends(pagination),
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[SmsOut]:
    stmt = select(SmsMessage)
    if status:
        stmt = stmt.where(SmsMessage.status == status)
    if phone:
        # Matched on the trailing digits so '9812345678' finds '+919812345678'.
        stmt = stmt.where(SmsMessage.to_phone.ilike(f"%{phone.strip().lstrip('+')}%"))
    if template_key:
        stmt = stmt.where(SmsMessage.template_key == template_key)
    if warranty_id:
        stmt = stmt.where(SmsMessage.warranty_id == warranty_id)
    if q:
        term = like(q)
        stmt = stmt.where(
            or_(SmsMessage.error.ilike(term), SmsMessage.provider_message_id.ilike(term))
        )

    start, end = day_window(date_from, date_to)
    if start is not None:
        stmt = stmt.where(SmsMessage.created_at >= start)
    if end is not None:
        stmt = stmt.where(SmsMessage.created_at < end)

    total = count_of(db, stmt)
    messages = db.execute(
        stmt.order_by(SmsMessage.created_at.desc()).limit(page.limit).offset(page.offset)
    ).scalars()
    return Paginated[SmsOut](
        items=[to_sms_out(m) for m in messages],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/sms/templates")
def list_templates(_: Admin = Depends(get_current_dealer_admin)) -> dict[str, dict[str, object]]:
    """The template registry, so the log's filter is not a free-text guess."""
    return {
        key: {"body": template.body, "variables": list(template.variables)}
        for key, template in sms_svc.TEMPLATES.items()
    }


@router.get("/sms/{message_id}", response_model=SmsOut)
def get_message(
    message_id: uuid.UUID,
    _: Admin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> SmsOut:
    message = db.get(SmsMessage, message_id)
    if message is None:
        raise AppError("message_not_found", 404, "No such message")
    return to_sms_out(message)


@router.post("/sms/{message_id}/retry", response_model=SmsOut)
def retry_message(
    message_id: uuid.UUID,
    request: Request,
    admin: Admin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> SmsOut:
    """Attempt delivery again.

    sms.flush never raises — a provider failure lands on the row, not on this
    request — so a retry that fails again returns the message with its new error
    and attempt count rather than a 500. It also commits, which is why the audit
    row is written first and rides along.
    """
    message = db.get(SmsMessage, message_id)
    if message is None:
        raise AppError("message_not_found", 404, "No such message")
    if message.status not in RETRYABLE:
        raise AppError(
            "not_retryable",
            409,
            f"A message that is '{message.status}' does not need retrying",
        )

    record_audit(
        db,
        action="retry_sms",
        entity_type="sms_message",
        entity_id=message.id,
        actor_id=admin.id,
        ip=client_ip(request),
        metadata={
            "to_phone": message.to_phone,
            "template_key": message.template_key,
            "previous_status": message.status,
            "attempts": message.attempts,
        },
    )
    sms_svc.flush(db, message.id)

    db.refresh(message)
    return to_sms_out(message)
