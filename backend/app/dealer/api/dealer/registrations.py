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
"""

import redis as redis_lib
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_current_staff, get_db, get_redis, idempotency_key
from app.core.errors import AppError
from app.dealer.models.allocation import Allocation
from app.dealer.models.dealer import DealerStaff
from app.dealer.models.warranty import Warranty
from app.dealer.schemas.registration import (
    CustomerBrief,
    RegisterIn,
    RegisterOut,
    UnitPreviewOut,
    WarrantyOut,
)
from app.dealer.services import idempotency, ledger, ratelimit, registration, sms
from app.dealer.services.unitsource import UnitSourceUnavailable, get_unit_source, normalise_serial
from app.models.product import Product
from app.models.product_unit import ProductUnit as Unit


def _unit_warranty_months(db: Session, unit: Unit | None) -> int:
    """Warranty length for a unit, from its product.

    Falls back to the configured default so a product nobody has set a length
    on still previews as sellable — refusing here would block a real sale over
    a missing admin setting.
    """
    if unit is None:
        return settings.default_warranty_months
    product = db.get(Product, unit.product_id)
    return (product.warranty_months if product else None) or settings.default_warranty_months


def _unit_model_name(db: Session, unit: Unit | None) -> str | None:
    """Product name for a unit. Lives on products, not on the unit row."""
    if unit is None:
        return None
    product = db.get(Product, unit.product_id)
    return product.name if product else None

router = APIRouter(tags=["dealer-registrations"])


@router.get("/units/{raw_serial}/preview", response_model=UnitPreviewOut)
def preview_unit(
    raw_serial: str,
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> UnitPreviewOut:
    """Answer 'can I sell this?' immediately after the scan.

    Deliberately tolerant: a preview that fails because upstream is down would
    stop the dealer before they even start typing, so every failure path here
    still returns `registerable` based on the allocation alone.
    """
    ratelimit.enforce(
        redis, f"preview:{staff.id}", limit=120, window_s=60, fail_open=True
    )
    serial = normalise_serial(raw_serial)

    existing = db.execute(
        select(Warranty).where(
            Warranty.serial == serial,
            Warranty.status.in_(
                ("pending_confirmation", "pending_review", "pending_backdate", "active", "claimed")
            ),
        )
    ).scalar_one_or_none()

    allocation = db.execute(
        select(Allocation).where(
            Allocation.serial == serial, Allocation.status.in_(("allocated", "registered"))
        )
    ).scalar_one_or_none()

    unit = db.execute(select(Unit).where(Unit.token == serial)).scalar_one_or_none()
    if unit is None:
        try:
            facts = get_unit_source(db).get(serial)
            if facts is not None:
                db.commit()
                unit = db.execute(select(Unit).where(Unit.token == serial)).scalar_one_or_none()
        except UnitSourceUnavailable:
            pass  # The allocation still decides; upstream is a nicety here.

    if existing is not None:
        mine = existing.dealer_id == staff.dealer_id
        return UnitPreviewOut(
            serial=serial,
            model_name=existing.model_name,
            warranty_months=existing.warranty_months,
            registerable=False,
            already_registered=True,
            reason=(
                "You already registered this unit"
                if mine
                else "This unit is already registered by another dealer"
            ),
        )
    if allocation is None:
        return UnitPreviewOut(
            serial=serial,
            model_name=_unit_model_name(db, unit) if unit else None,
            warranty_months=_unit_warranty_months(db, unit),
            registerable=False,
            reason="This unit is not allocated to any dealer",
        )
    if allocation.dealer_id != staff.dealer_id:
        return UnitPreviewOut(
            serial=serial,
            model_name=_unit_model_name(db, unit) if unit else None,
            warranty_months=_unit_warranty_months(db, unit),
            registerable=False,
            reason="This unit is allocated to a different dealer",
        )

    return UnitPreviewOut(
        serial=serial,
        model_name=_unit_model_name(db, unit) if unit else None,
        warranty_months=_unit_warranty_months(db, unit),
        registerable=True,
    )


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
            raw_serial=body.serial,
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
                    "serial": warranty.serial[:12],
                    "link": f"{settings.public_base_url}/w/{warranty.id}",
                },
                warranty_id=warranty.id,
            )
        message_id = message.id if message else None

        out = RegisterOut(
            warranty=WarrantyOut.model_validate(warranty),
            customer=CustomerBrief(
                name=warranty.customer.name, phone=warranty.customer.phone
            ),
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
