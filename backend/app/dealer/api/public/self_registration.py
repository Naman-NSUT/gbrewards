"""Customer self-registration endpoint.

Mount: `api_router.include_router(self_registration.router, prefix="/public")`.

Multipart, because the invoice photo is the point: a self-registration without
proof is an anonymous assertion that a sale happened, and the admin working the
queue would have nothing to judge. See services/self_registration.py for why this
pays nobody and always waits for a human, and services/storage.py for how an
anonymous upload is made safe.

Order of operations matters. The duplicate check runs BEFORE the upload is
stored, so the common "my dealer did register it after all" case never puts a
file in the store, and any failure after it is stored discards it rather than
leaving an orphan the approval queue will never reference.
"""

from datetime import date
from typing import Annotated

import redis as redis_lib
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_db, get_redis
from app.core.errors import AppError
from app.dealer.schemas.public import SelfRegistrationIn, SelfRegistrationOut, redact
from app.dealer.services import ratelimit, storage
from app.dealer.services import self_registration as self_reg

router = APIRouter(tags=["public"])

# Tighter than the lookup limit: an unauthenticated WRITE that creates work for a
# human. The ceiling is "a household with several mattresses, plus retries", not
# "a browsing session".
_PER_IP_PER_DAY = 10
_PER_PHONE_PER_DAY = 5


def _validated(**fields: object) -> SelfRegistrationIn:
    """Apply the schema by hand, converting failures to the standard envelope.

    The form is NOT bound as a FastAPI `Form()` model, deliberately. A form model
    reports a missing or invalid field with the whole parsed body as the error
    `input` — and on a multipart request that body contains the UploadFile
    object, which the shared RequestValidationError handler cannot serialise. The
    result would be a 500 on the single most common user mistake (forgetting a
    field) in the most valuable flow in the system. Declaring the fields
    individually keeps every error payload to strings, and this function keeps
    the phone normalisation and the purchase-date policy in the schema where the
    rest of the system looks for them.
    """
    try:
        return SelfRegistrationIn(**fields)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise AppError(
            "validation_error",
            422,
            "Request validation failed",
            {
                "errors": [
                    {
                        "loc": [str(part) for part in error["loc"]],
                        "msg": error["msg"],
                        "type": error["type"],
                    }
                    for error in exc.errors()
                ]
            },
        ) from exc


@router.post("/self-registrations", response_model=SelfRegistrationOut, status_code=201)
def create_self_registration(
    request: Request,
    response: Response,
    serial: Annotated[str, Form(min_length=1, max_length=200)],
    customer_phone: Annotated[str, Form(min_length=6, max_length=20)],
    customer_name: Annotated[str, Form(min_length=1, max_length=200)],
    purchase_date: Annotated[date, Form()],
    proof: Annotated[UploadFile, File(description="Photo or PDF of the purchase invoice")],
    invoice_ref: Annotated[str | None, Form(max_length=120)] = None,
    dealer_hint: Annotated[str | None, Form(max_length=200)] = None,
    customer_address: Annotated[str | None, Form(max_length=400)] = None,
    customer_city: Annotated[str | None, Form(max_length=100)] = None,
    customer_state: Annotated[str | None, Form(max_length=100)] = None,
    customer_pincode: Annotated[str | None, Form(max_length=10)] = None,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> SelfRegistrationOut:
    body = _validated(
        serial=serial,
        customer_phone=customer_phone,
        customer_name=customer_name,
        purchase_date=purchase_date,
        invoice_ref=invoice_ref,
        dealer_hint=dealer_hint,
        customer_address=customer_address,
        customer_city=customer_city,
        customer_state=customer_state,
        customer_pincode=customer_pincode,
    )

    ip = client_ip(request)
    ratelimit.enforce(
        redis, f"selfreg:ip:{ip}", limit=_PER_IP_PER_DAY, window_s=86400, fail_open=False
    )
    ratelimit.enforce(
        redis,
        f"selfreg:phone:{body.customer_phone}",
        limit=_PER_PHONE_PER_DAY,
        window_s=86400,
        fail_open=False,
    )

    normalised_serial = self_reg.normalise(body.serial)

    existing = self_reg.live_warranty(db, normalised_serial)
    if existing is not None:
        # Already registered — by the dealer, or by this customer a moment ago.
        # Answered with the redacted record rather than an error: "it is already
        # covered" is good news, and the masked record lets them recognise their
        # own purchase without exposing anything to someone guessing serials.
        response.status_code = 200
        return SelfRegistrationOut(
            status="already_registered",
            warranty=redact(existing, dealer=self_reg.selling_dealer(db, existing)),
            message=(
                "This mattress is already registered. If the details shown are not yours, "
                "contact GoodBed support."
            ),
        )

    stored = storage.save_upload(proof)
    try:
        result = self_reg.submit(
            db,
            raw_serial=normalised_serial,
            customer_phone=body.customer_phone,
            customer_name=body.customer_name,
            purchase_date=body.purchase_date,
            proof_key=stored.key,
            invoice_ref=body.invoice_ref,
            dealer_hint=body.dealer_hint,
            customer_address=body.customer_address,
            customer_city=body.customer_city,
            customer_state=body.customer_state,
            customer_pincode=body.customer_pincode,
            ip=ip,
        )
        out = SelfRegistrationOut(
            status="submitted",
            warranty=redact(result.warranty, dealer=result.dealer),
            message=(
                "Thank you. Your warranty has been submitted for verification with your "
                "invoice, and we will confirm by SMS once our team has reviewed it."
            ),
        )
        db.commit()
    except Exception:
        # Nothing points at the file, so it must not survive the failure.
        db.rollback()
        storage.discard(stored.key)
        raise

    return out
