"""The dealer's window to fix a mistyped customer number.

THE DECISION: a dealer may correct the customer's name and mobile on their own
registration for DEALER_EDIT_WINDOW_HOURS (default 24), after which it is
admin-only. Every edit is audited with the before and after values, inside the
window or not.

Why a window at all: mistyping a digit of a mobile number at a busy counter is
the single most likely data error in this system, and it is silently
catastrophic — the customer never gets the SMS, cannot find their warranty, and
eventually self-registers, which then reads as dealer non-compliance. Making the
dealer wait for an admin to fix a typo they noticed ten seconds later would be
absurd.

Why the window closes: after a day, an edit is no longer plausibly a typo. It is
a warranty being reassigned to a different person, which is exactly how a dealer
would launder a fake registration into a real one once a real buyer appeared. So
past the window it needs a human at the brand, with a reason.

What can NEVER be edited by a dealer, in or out of the window: the serial, the
dates, or which dealer owns the registration. Only who the customer is.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_current_staff, get_db
from app.core.errors import AppError
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import DealerStaff
from app.dealer.models.warranty import Warranty, WarrantyEvent
from app.dealer.schemas.common import Base, PhoneMixin
from app.dealer.schemas.registration import WarrantyOut
from app.dealer.services import sms
from app.dealer.services.audit import record_audit

router = APIRouter(tags=["dealer-corrections"])


class CorrectionIn(PhoneMixin, Base):
    customer_phone: str | None = Field(default=None, min_length=6, max_length=20)
    customer_name: str | None = Field(default=None, min_length=1, max_length=200)


class CorrectionOut(Base):
    warranty: WarrantyOut
    customer_name: str
    customer_phone: str
    resent_sms: bool


@router.patch("/registrations/{warranty_id}/customer", response_model=CorrectionOut)
def correct_customer(
    # uuid.UUID, not str: a junk path segment typed as a string is handed
    # straight to db.get(), where psycopg raises "invalid input syntax for type
    # uuid" — a 500 with the request's transaction already dead, over a fat
    # finger. It also breaks the defence three lines below: that 404 exists to
    # give "no such registration" and "another dealer's registration" the same
    # answer, and a crash on a malformed id is a third, handler-level answer for
    # a prober to sort ids by. Typed as a UUID the id is rejected by validation
    # before any lookup, so it says nothing about what is in the database.
    warranty_id: uuid.UUID,
    body: CorrectionIn,
    request: Request,
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> CorrectionOut:
    if body.customer_phone is None and body.customer_name is None:
        raise AppError("nothing_to_change", 400, "Provide a name or a mobile number")

    warranty = db.get(Warranty, warranty_id)
    if warranty is None or warranty.dealer_id != staff.dealer_id:
        # Same answer for "does not exist" and "belongs to another dealer", so
        # this cannot be used to probe other dealers' registrations.
        raise AppError("not_found", 404, "Registration not found")

    if warranty.status == "voided":
        raise AppError("warranty_voided", 409, "This registration has been cancelled")

    age = datetime.now(UTC) - warranty.registered_at
    if age > timedelta(hours=settings.dealer_edit_window_hours):
        raise AppError(
            "edit_window_closed",
            403,
            (
                f"Customer details can only be corrected within "
                f"{settings.dealer_edit_window_hours} hours. Contact GoodBed support."
            ),
            {"registered_at": warranty.registered_at.isoformat()},
        )

    before = {"name": warranty.customer.name, "phone": warranty.customer.phone}

    # Moving the warranty to a DIFFERENT customer record, rather than editing the
    # existing one in place: the old customer may own other mattresses, and
    # rewriting their phone number here would corrupt those too.
    resent = False
    if body.customer_phone and body.customer_phone != warranty.customer.phone:
        target = db.execute(
            select(Customer).where(Customer.phone == body.customer_phone)
        ).scalar_one_or_none()
        if target is None:
            target = Customer(
                phone=body.customer_phone,
                name=body.customer_name or warranty.customer.name,
            )
            db.add(target)
            db.flush()
        warranty.customer_id = target.id
        if body.customer_name:
            target.name = body.customer_name
        resent = True
    elif body.customer_name:
        warranty.customer.name = body.customer_name

    db.flush()
    db.refresh(warranty)

    after = {"name": warranty.customer.name, "phone": warranty.customer.phone}

    db.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event="customer_corrected",
            from_status=warranty.status,
            to_status=warranty.status,
            actor_type="dealer_staff",
            actor_id=staff.id,
            reason="Dealer correction within edit window",
            event_metadata={"before": before, "after": after},
        )
    )
    record_audit(
        db,
        action="edit_customer",
        entity_type="warranty",
        entity_id=warranty.id,
        actor_type="dealer_staff",
        actor_id=staff.id,
        reason="Dealer correction within edit window",
        metadata={"before": before, "after": after},
        ip=client_ip(request),
    )

    message = None
    if resent and warranty.status == "active":
        # The whole point of fixing the number is that the customer gets the SMS.
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
    db.commit()

    if message_id is not None:
        sms.flush(db, message_id)

    return CorrectionOut(
        warranty=WarrantyOut.model_validate(warranty),
        customer_name=warranty.customer.name,
        customer_phone=warranty.customer.phone,
        resent_sms=resent,
    )
