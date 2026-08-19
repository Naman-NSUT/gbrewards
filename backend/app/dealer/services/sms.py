"""Outbound SMS: provider abstraction, template registry, delivery log.

Two things are deliberately different from GB Rewards here.

1. GB Rewards' provider interface is `send(phone, code)` — OTP-shaped. It cannot
   express "send this customer their warranty details", which is the message
   this product exists to send. The interface here is message-shaped:
   `send(phone, template, variables)`.

2. GB Rewards sends fire-and-forget with nothing persisted, so "did the customer
   get the SMS?" is unanswerable. Here every send is a row BEFORE the HTTP call,
   and the provider's answer is written back onto it. That row is the admin SMS
   log screen.

INDIA DLT — ON THE CRITICAL PATH. Every template must be registered and approved
on the operator's DLT portal before it can be delivered, and approval takes days.
GB Rewards has exactly ONE approved template, an OTP one ("OTP1" on 2Factor), and
it cannot carry warranty variables. So the templates below need their own DLT
registration and that should be started before any of this code matters. Until
they are approved, run SMS_PROVIDER=fake: everything is logged and visible in the
admin screen, nothing is delivered, and no other work is blocked.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.dealer.models.sms_message import SmsMessage

logger = get_logger(__name__)


@dataclass(frozen=True)
class Template:
    key: str
    # The exact text submitted for DLT approval. Variables in {} must match the
    # registered template EXACTLY or the operator silently drops the message.
    body: str
    variables: tuple[str, ...]


TEMPLATES: dict[str, Template] = {
    "warranty_registered": Template(
        key="warranty_registered",
        body=(
            "Dear {name}, your GoodBed warranty is registered. "
            "Model {model}, valid till {end_date}. Ref {serial}. "
            "View or raise a claim: {link}"
        ),
        variables=("name", "model", "end_date", "serial", "link"),
    ),
    "warranty_voided": Template(
        key="warranty_voided",
        body=(
            "Dear {name}, the GoodBed warranty on {serial} has been cancelled. "
            "Contact your dealer or visit {link} if this is unexpected."
        ),
        variables=("name", "serial", "link"),
    ),
    "claim_received": Template(
        key="claim_received",
        body=(
            "Dear {name}, we have received your GoodBed warranty claim {reference}. "
            "Track it at {link}"
        ),
        variables=("name", "reference", "link"),
    ),
    "login_otp": Template(
        key="login_otp",
        body="{otp} is your GoodBed Dealer login code. Valid {minutes} minutes.",
        variables=("otp", "minutes"),
    ),
}


class SmsProvider(ABC):
    name = "abstract"

    @abstractmethod
    def send(self, phone: str, template: Template, variables: dict[str, Any]) -> str | None:
        """Deliver a message. Return a provider message id if one is given.

        Raise on failure — the caller records the error on the log row.
        """


class FakeSmsProvider(SmsProvider):
    """Logs instead of sending. The default, and the only safe setting until DLT
    templates are approved."""

    name = "fake"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict[str, Any]]] = []

    def send(self, phone: str, template: Template, variables: dict[str, Any]) -> str | None:
        rendered = template.body.format(**{k: variables.get(k, "") for k in template.variables})
        self.sent.append((phone, template.key, dict(variables)))
        logger.info("fake_sms to=%s template=%s body=%s", phone, template.key, rendered)
        return f"fake-{uuid.uuid4()}"


class Msg91Provider(SmsProvider):
    """MSG91 flow API — chosen over 2Factor for transactional templates.

    2Factor's template endpoint used by GB Rewards takes a single OTP value in
    the URL path and cannot carry the five variables a warranty confirmation
    needs. MSG91's flow API takes named variables against a DLT template id,
    which is the shape this product requires.
    """

    name = "msg91"
    URL = "https://control.msg91.com/api/v5/flow/"

    def send(self, phone: str, template: Template, variables: dict[str, Any]) -> str | None:
        template_id = (
            settings.msg91_otp_template_id
            if template.key == "login_otp"
            else settings.msg91_warranty_template_id
        )
        if not template_id:
            raise RuntimeError(f"No DLT template id configured for '{template.key}'")

        recipient: dict[str, Any] = {"mobiles": phone.lstrip("+")}
        recipient.update({k: str(variables.get(k, "")) for k in template.variables})

        resp = httpx.post(
            self.URL,
            json={
                "template_id": template_id,
                "sender": settings.sms_sender_id,
                "short_url": "0",
                "recipients": [recipient],
            },
            headers={"authkey": settings.msg91_auth_key, "Content-Type": "application/json"},
            timeout=settings.sms_timeout_seconds,
        )
        if resp.is_error:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json() if resp.text else {}
        if str(data.get("type", "")).lower() == "error":
            raise RuntimeError(str(data.get("message", "provider rejected the message"))[:200])
        return str(data.get("request_id") or "") or None


_provider: SmsProvider | None = None


def get_provider() -> SmsProvider:
    global _provider
    if _provider is None:
        _provider = Msg91Provider() if settings.sms_provider == "msg91" else FakeSmsProvider()
    return _provider


def queue(
    session: Session,
    *,
    phone: str,
    template_key: str,
    variables: dict[str, Any],
    warranty_id: uuid.UUID | None = None,
) -> SmsMessage:
    """Record the intent to send, inside the caller's transaction.

    Queue-then-send, rather than send-then-record, so a provider that hangs never
    holds a database transaction open while a dealer waits — and so a message
    that was attempted is visible even if the process dies before it completes.
    """
    if template_key not in TEMPLATES:
        raise KeyError(f"Unknown SMS template '{template_key}'")
    message = SmsMessage(
        to_phone=phone,
        template_key=template_key,
        provider=settings.sms_provider,
        variables=variables,
        status="queued",
        warranty_id=warranty_id,
    )
    session.add(message)
    session.flush()
    return message


def flush(session: Session, message_id: uuid.UUID) -> None:
    """Attempt delivery of one queued message. Safe to call after commit.

    Never raises: a failed SMS must not undo a completed sale. The failure lands
    on the row and on the admin screen, where someone can retry it.
    """
    message = session.get(SmsMessage, message_id)
    if message is None or message.status in ("sent", "delivered"):
        return
    template = TEMPLATES[message.template_key]
    provider = get_provider()
    message.attempts += 1
    try:
        provider_id = provider.send(message.to_phone, template, message.variables or {})
        message.status = "sent"
        message.provider_message_id = provider_id
        message.provider_template_id = (
            settings.msg91_otp_template_id
            if template.key == "login_otp"
            else settings.msg91_warranty_template_id
        ) or None
        message.sent_at = datetime.now(UTC)
        message.error = None
    except Exception as exc:  # noqa: BLE001 - deliberate: delivery must never raise
        message.status = "failed"
        message.error = str(exc)[:500]
        logger.warning("sms_send_failed id=%s err=%s", message_id, exc)
    session.add(message)
    session.commit()
