"""The link in the warranty SMS: {public_base_url}/w/{warranty_id}.

Mount: `api_router.include_router(confirm.router, prefix="/public")`.

This is where the sale record stops being the dealer's word and becomes the
customer's too. Three actions, and the interesting decisions are in the last two.

THE POSSESSION CHECK. The warranty id is a UUID in an SMS, and an SMS gets
forwarded, screenshotted, and read by whoever picks the phone up. So every action
here also requires the last four digits of the registered mobile. That is not a
password — it is a second factor the real customer has in their hand and a leaked
link does not carry. Brute force is the obvious objection to a four-digit secret,
so WRONG guesses (only wrong ones) burn a per-warranty budget: a legitimate
customer never consumes it, and an attacker gets ten attempts an hour against a
10,000-space, which is ~40 days per warranty for a value that is worthless
elsewhere.

DISPUTE DOES NOT VOID. It would be one line, and it would be a hole big enough to
drive the whole product through: anyone holding a link — a forwarded SMS, a
returned handset, an ex-employee at the shop — could destroy a real sale record,
claw back a dealer's points, and free the serial for re-registration. Worse, the
damage is silent, because the person who loses is the customer who is not
watching. So a dispute records what the customer said (a WarrantyEvent plus an
audit row) and puts the record in front of a human who can look at the invoice.
The asymmetry is the point: confirming is safe to automate because it can only
strengthen a record; voiding destroys one, so it stays with an admin who is
accountable for the reason string.
"""

import secrets
import uuid

import redis as redis_lib
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_db, get_redis
from app.core.errors import AppError
from app.dealer.models.warranty import Warranty, WarrantyEvent
from app.dealer.schemas.public import (
    CustomerActionOut,
    DisputeIn,
    Last4In,
    WarrantyViewOut,
    redact,
)
from app.dealer.services import ratelimit
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.audit import record_audit
from app.dealer.services.self_registration import selling_dealer

router = APIRouter(tags=["public"])

# Wrong-guess budget per warranty. Only failures count, so this never gets in a
# real customer's way; it is what stops the four-digit check being brute-forced.
_LAST4_ATTEMPTS_PER_HOUR = 10
_ACTIONS_PER_IP_PER_DAY = 30

_INVALID = "That link is not valid, or the last 4 digits do not match this warranty."


def _load_guarded(
    db: Session,
    redis: redis_lib.Redis,
    *,
    warranty_id: uuid.UUID,
    last4: str,
    ip: str,
) -> Warranty:
    """Fetch a warranty for a customer holding the SMS link, or refuse."""
    ratelimit.enforce(
        redis,
        f"public:w:{ip}",
        limit=settings.public_lookup_per_min_per_ip,
        window_s=60,
        fail_open=False,
    )

    warranty = db.get(Warranty, warranty_id)
    digits = "".join(ch for ch in (warranty.customer.phone if warranty else "") if ch.isdigit())
    expected = digits[-4:] if len(digits) >= 4 else ""
    matched = bool(expected) and secrets.compare_digest(expected, last4)

    # An unknown id and a wrong code fail identically: a caller must not be able
    # to test whether a warranty id exists by reading the error.
    if warranty is None or not matched:
        ratelimit.enforce(
            redis,
            f"public:w:last4:{warranty_id}",
            limit=_LAST4_ATTEMPTS_PER_HOUR,
            window_s=3600,
            fail_open=False,
        )
        raise AppError("invalid_link", 403, _INVALID)

    return warranty


def _view(db: Session, warranty: Warranty, message: str) -> CustomerActionOut:
    return CustomerActionOut(
        warranty=redact(warranty, dealer=selling_dealer(db, warranty)),
        message=message,
    )


@router.get("/w/{warranty_id}", response_model=WarrantyViewOut)
def view_warranty(
    warranty_id: uuid.UUID,
    request: Request,
    # [0-9] rather than \d: \d also matches Devanagari and other Unicode digits,
    # which would reach the constant-time compare below and raise there.
    last4: str = Query(min_length=4, max_length=4, pattern=r"^[0-9]{4}$"),
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> WarrantyViewOut:
    warranty = _load_guarded(db, redis, warranty_id=warranty_id, last4=last4, ip=client_ip(request))
    return WarrantyViewOut(
        warranty=redact(warranty, dealer=selling_dealer(db, warranty)),
        awaiting_confirmation=warranty.status == "pending_confirmation",
        already_confirmed=warranty.confirmed_at is not None or warranty.customer.is_phone_verified,
    )


@router.post("/w/{warranty_id}/confirm", response_model=CustomerActionOut)
def confirm_warranty(
    warranty_id: uuid.UUID,
    body: Last4In,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> CustomerActionOut:
    ip = client_ip(request)
    ratelimit.enforce(redis, f"public:confirm:{ip}", limit=_ACTIONS_PER_IP_PER_DAY, window_s=86400)
    warranty = _load_guarded(db, redis, warranty_id=warranty_id, last4=body.last4, ip=ip)

    if warranty.status == "voided":
        raise AppError(
            "warranty_voided",
            409,
            "This warranty has been cancelled. Contact GoodBed support if that is unexpected.",
        )

    # Activates and credits the dealer when the warranty was waiting on this
    # confirmation; a no-op in every other state.
    warranty_svc.confirm(db, warranty=warranty, actor_type="customer")

    # REQUIRE_CUSTOMER_CONFIRMATION is off by default, so most warranties are
    # already 'active' when the customer taps confirm and the call above does
    # nothing. The acknowledgement is still worth recording: is_phone_verified is
    # the difference between "a dealer typed this number" and "the person holding
    # it agreed", which is exactly what a disputed claim turns on years later.
    if warranty.status == "active" and not warranty.customer.is_phone_verified:
        warranty.customer.is_phone_verified = True
        db.add(
            WarrantyEvent(
                warranty_id=warranty.id,
                event="customer_verified",
                from_status=warranty.status,
                to_status=warranty.status,
                actor_type="customer",
                actor_id=warranty.customer_id,
                event_metadata={"ip": ip},
            )
        )

    out = _view(
        db,
        warranty,
        "Thank you — your warranty is confirmed. Keep this link to raise a claim later.",
    )
    db.commit()
    return out


@router.post("/w/{warranty_id}/dispute", response_model=CustomerActionOut)
def dispute_warranty(
    warranty_id: uuid.UUID,
    body: DisputeIn,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> CustomerActionOut:
    ip = client_ip(request)
    ratelimit.enforce(redis, f"public:dispute:{ip}", limit=_ACTIONS_PER_IP_PER_DAY, window_s=86400)
    warranty = _load_guarded(db, redis, warranty_id=warranty_id, last4=body.last4, ip=ip)

    if warranty.status == "voided":
        return _view(
            db,
            warranty,
            "This warranty has already been cancelled, so there is nothing to dispute.",
        )

    reason = (body.note or "").strip() or "Customer disputed this sale from the SMS link"

    # No status change, on purpose — see the module docstring. The event is what
    # the admin approvals queue filters on (event='disputed'), and the audit row
    # is what makes the decision explicable months later.
    db.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event="disputed",
            from_status=warranty.status,
            to_status=warranty.status,
            actor_type="customer",
            actor_id=warranty.customer_id,
            reason=reason,
            event_metadata={"serial": warranty.serial, "ip": ip},
        )
    )
    record_audit(
        db,
        action="dispute_warranty",
        entity_type="warranty",
        entity_id=warranty.id,
        actor_type="customer",
        actor_id=warranty.customer_id,
        reason=reason,
        metadata={"serial": warranty.serial, "status": warranty.status},
        ip=ip,
    )

    out = _view(
        db,
        warranty,
        "Thank you. We have recorded that you did not make this purchase and our team "
        "will review it. The record stays as it is until a person has checked it, so "
        "nobody can cancel a genuine warranty from this link.",
    )
    db.commit()
    return out
