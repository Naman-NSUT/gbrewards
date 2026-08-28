"""The endpoint a dealer hits at the counter.

Shape of the request, and why:

  * Idempotency-Key header is REQUIRED. The mobile app queues submissions
    offline and replays them; without a key, a replay is indistinguishable from
    a second sale. Making it optional would mean the guarantee only holds for
    well-behaved clients, which is no guarantee at all.
  * The transaction boundary is here, not in the service, so the service stays
    composable (admin tools reuse `register()` inside their own transactions).
  * The SMS is sent AFTER commit. A slow provider must not hold a transaction
    open while a customer waits, and a failed SMS must not undo a real sale.

Nothing is scanned any more, so there is no longer a preview step. The scanner
asked "can I sell this?" about a specific physical label and this module
answered from `dealer_units`; a dropdown cannot be pointed at a mattress that
does not exist, so the question no longer has a subject. What may be sold is
GET /dealer/products, and what stops the same sale being registered twice is
the invoice number, checked inside register().
"""

import redis as redis_lib
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_current_staff, get_db, get_redis, idempotency_key
from app.core.errors import AppError
from app.dealer.models.dealer import DealerStaff
from app.dealer.models.warranty import Warranty
from app.dealer.schemas.registration import CustomerBrief, RegisterIn, RegisterOut, WarrantyOut
from app.dealer.services import idempotency, ledger, ratelimit, registration, sms

router = APIRouter(tags=["dealer-registrations"])


@router.post("/registrations", response_model=RegisterOut, status_code=201)
def create_registration(
    body: RegisterIn,
    request: Request,
    response: Response,
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
    key: str | None = Depends(idempotency_key),
) -> RegisterOut:
    if not key:
        raise AppError(
            "idempotency_key_required",
            400,
            "An Idempotency-Key header is required for registrations",
        )

    # Velocity limits. Fail CLOSED: if we cannot count, we do not pay.
    ratelimit.enforce(
        redis,
        f"reg:staff:{staff.id}",
        limit=settings.registrations_per_hour_per_staff,
        window_s=3600,
    )
    ratelimit.enforce(
        redis,
        f"reg:dealer:{staff.dealer_id}",
        limit=settings.registrations_per_day_per_dealer,
        window_s=86400,
    )

    payload = body.model_dump(mode="json")
    try:
        idempotency.claim_key(
            db,
            key=key,
            dealer_id=staff.dealer_id,
            endpoint="POST /dealer/registrations",
            payload=payload,
        )
    except idempotency.Replay as replay:
        response.status_code = replay.status
        return RegisterOut.model_validate(replay.body)

    try:
        result = registration.register(
            db,
            staff=staff,
            product_id=body.product_id,
            customer_phone=body.customer_phone,
            customer_name=body.customer_name,
            invoice_ref=body.invoice_ref,
            invoice_date=body.invoice_date,
            customer_address=body.customer_address,
            customer_city=body.customer_city,
            customer_state=body.customer_state,
            customer_pincode=body.customer_pincode,
        )

        warranty = result.warranty
        message = None
        if warranty.status == "active":
            message = sms.queue(
                db,
                phone=warranty.customer.phone,
                template_key="warranty_registered",
                variables={
                    "name": warranty.customer.name,
                    "model": warranty.model_name or "your GoodBed mattress",
                    "end_date": warranty.warranty_end_date.strftime("%d-%m-%Y"),
                    # {serial} is the reference the customer quotes when they
                    # ring about this warranty, and the template's wording is
                    # fixed by DLT approval. There is no serial any more, so
                    # that reference is the invoice number on the bill in their
                    # hand. Only the old 36-character serials were truncated —
                    # half an invoice number is not a reference anyone can look
                    # up.
                    "serial": (
                        warranty.serial[:12] if warranty.serial else (warranty.invoice_ref or "")
                    ),
                    "link": f"{settings.public_base_url}/w/{warranty.id}",
                },
                warranty_id=warranty.id,
            )
        message_id = message.id if message else None

        out = RegisterOut(
            warranty=WarrantyOut.model_validate(warranty),
            customer=CustomerBrief(name=warranty.customer.name, phone=warranty.customer.phone),
            points_awarded=result.points_awarded,
            balance=result.balance,
            idempotent=result.idempotent,
            unit_unverified=result.unit_unverified,
        )
        db.commit()
    except Exception:
        # Free the key so the dealer can genuinely retry, rather than being told
        # "still processing" forever for a sale that never happened.
        idempotency.release_key(db, key=key, dealer_id=staff.dealer_id)
        raise

    idempotency.complete_key(
        db,
        key=key,
        dealer_id=staff.dealer_id,
        status=201,
        body=out.model_dump(mode="json"),
    )

    # Outside the transaction, on purpose. Failure here is logged on the message
    # row and retried from the admin SMS screen; it cannot undo the sale.
    if message_id is not None:
        sms.flush(db, message_id)

    _ = client_ip(request)
    return out


@router.get("/registrations", response_model=list[WarrantyOut])
def list_registrations(
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> list[Warranty]:
    stmt = (
        select(Warranty)
        .where(Warranty.dealer_id == staff.dealer_id)
        .order_by(Warranty.registered_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


@router.get("/points")
def points_summary(
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return {
        "balance": ledger.balance(db, staff.dealer_id),
        "pending": ledger.pending(db, staff.dealer_id),
        "available": ledger.available(db, staff.dealer_id),
        "total_earned": ledger.total_earned(db, staff.dealer_id),
    }
