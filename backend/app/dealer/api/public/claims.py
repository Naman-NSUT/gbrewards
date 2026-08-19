"""Public claim submission and status check.

Mount: `api_router.include_router(claims.router, prefix="/public")`.

Both endpoints require the registered mobile number as well as the identifier
(serial for a new claim, reference for a status check) — see services/claims.py
for why, and for why every failure returns the same message.

The SMS is queued inside the transaction and sent after commit, matching the
dealer registration flow: a slow provider must not hold a transaction open, and
a failed SMS must not undo a claim the customer has already been told we have.
"""

import redis as redis_lib
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_db, get_redis
from app.dealer.schemas.public import ClaimIn, ClaimOut, ClaimStatusIn, redact
from app.dealer.services import claims as claims_svc
from app.dealer.services import ratelimit, sms
from app.dealer.services.self_registration import selling_dealer

router = APIRouter(tags=["public"])

_CLAIMS_PER_IP_PER_DAY = 10

_STATUS_MESSAGES = {
    "open": "We have your claim and it is waiting to be picked up by our team.",
    "in_review": "Our team is reviewing your claim.",
    "approved": "Your claim has been approved. Our team will arrange the next step.",
    "rejected": "Your claim was not approved. See the note below, or contact support.",
    "closed": "This claim has been closed.",
}


def _claim_link(reference: str) -> str:
    return f"{settings.public_base_url}/claims/{reference}"


@router.post("/claims", response_model=ClaimOut, status_code=201)
def create_claim(
    body: ClaimIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> ClaimOut:
    ip = client_ip(request)
    # Fail closed: an unauthenticated write that puts work in a human's queue.
    ratelimit.enforce(
        redis, f"claim:ip:{ip}", limit=_CLAIMS_PER_IP_PER_DAY, window_s=86400, fail_open=False
    )

    result = claims_svc.submit(
        db,
        raw_serial=body.serial,
        phone=body.phone,
        description=body.description,
        issue_type=body.issue_type,
        ip=ip,
    )
    claim, warranty = result.claim, result.warranty

    message_id = None
    if result.duplicate:
        # A second submission against an already-open claim is the same person
        # chasing it. No new record, and no second SMS.
        response.status_code = 200
        text = (
            f"You already have an open claim ({claim.reference}) for this mattress. "
            "Our team is working on it and will contact you."
        )
    else:
        text = (
            f"Your claim has been raised. Quote reference {claim.reference} when you "
            "contact us — we have sent it to your mobile as well."
        )
        message = sms.queue(
            db,
            phone=warranty.customer.phone,
            template_key="claim_received",
            variables={
                "name": warranty.customer.name,
                "reference": claim.reference,
                "link": _claim_link(claim.reference),
            },
            warranty_id=warranty.id,
        )
        message_id = message.id

    out = ClaimOut(
        reference=claim.reference,
        status=claim.status,
        issue_type=claim.issue_type,
        description=claim.description,
        created_at=claim.created_at,
        resolution_note=claim.resolution_note,
        resolved_at=claim.resolved_at,
        warranty=redact(warranty, dealer=selling_dealer(db, warranty)),
        message=text,
    )
    db.commit()

    # After commit, on purpose. A provider failure lands on the message row and
    # the admin SMS screen; it cannot undo the claim.
    if message_id is not None:
        sms.flush(db, message_id)

    return out


@router.post("/claims/status", response_model=ClaimOut)
def claim_status(
    body: ClaimStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> ClaimOut:
    ratelimit.enforce(
        redis,
        f"public:claimstatus:{client_ip(request)}",
        limit=settings.public_lookup_per_min_per_ip,
        window_s=60,
        fail_open=False,
    )

    claim, warranty = claims_svc.find_for_status(db, reference=body.reference, phone=body.phone)
    return ClaimOut(
        reference=claim.reference,
        status=claim.status,
        issue_type=claim.issue_type,
        description=claim.description,
        created_at=claim.created_at,
        resolution_note=claim.resolution_note,
        resolved_at=claim.resolved_at,
        warranty=redact(warranty, dealer=selling_dealer(db, warranty)),
        message=_STATUS_MESSAGES.get(claim.status, "Your claim is with our team."),
    )
