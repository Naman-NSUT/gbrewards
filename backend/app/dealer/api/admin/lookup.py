"""THE unified serial lookup — the screen support staff live on.

A customer rings with a serial off a label. In one response this returns
everything that has ever been true about that serial: the unit as the mirror
knows it (and how much to trust it), who was allocated it and who holds it now,
the live warranty with its buyer and seller, every warranty it has ever carried
including voided ones, the claim history, every SMS sent about it and the merged
event timeline.

Completeness is the feature. Anything left out becomes a second query in a
second tab while a customer waits on the phone, and the support desk's real
alternative to this screen is asking the client's office to look in a
spreadsheet.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.core.errors import AppError
from app.dealer.api.admin._common import (
    allocation_select,
    to_allocation_out,
    to_warranty_item,
    warranty_select,
)
from app.dealer.api.admin.claims import claim_select, to_claim_item
from app.dealer.api.admin.sms import to_sms_out
from app.dealer.api.admin.warranties import build_warranty_detail, resolve_actor_names
from app.dealer.models.allocation import Allocation
from app.dealer.models.claim import Claim
from app.dealer.models.sms_message import SmsMessage
from app.dealer.models.warranty import LIVE_STATUSES, Warranty, WarrantyEvent
from app.dealer.schemas.admin import (
    ClaimListItem,
    SerialLookupOut,
    SmsOut,
    UnitOut,
    WarrantyEventOut,
)
from app.dealer.services.unitsource import get_unit_source, normalise_serial
from app.models.admin import Admin
from app.models.product import Product
from app.models.product_unit import ProductUnit as Unit


def _unit_model_name(db: Session, unit: Unit | None) -> str | None:
    """Product name for a unit. Lives on products, not on the unit row."""
    if unit is None:
        return None
    product = db.get(Product, unit.product_id)
    return product.name if product else None

router = APIRouter(tags=["admin-lookup"])


def _unit_out(db: Session, serial: str) -> UnitOut:
    """The manufactured unit behind a serial.

    No mirror, no staleness, no read-through: `product_units` is the source, in
    the same database. The fields that used to describe cache freshness are
    reported as their now-constant truths so the admin response shape stays
    stable for the panel.
    """
    facts = get_unit_source(db).get(serial)
    if facts is None:
        return UnitOut(known=False, serial=serial)

    return UnitOut(
        known=True,
        serial=facts.serial,
        model_name=facts.model_name,
        model_code=facts.model_code,
        warranty_months=facts.warranty_months,
        source="gbrewards",
        # Manufacturing's own lifecycle value ('active'/'claimed'/'void'). NOT a
        # sale status: a worker scanning at assembly sets 'claimed' long before
        # the mattress reaches a shop.
        source_status=facts.source_status,
        source_synced_at=None,
        unverified=False,
        stale=False,
    )



@router.get("/lookup/{raw_serial:path}", response_model=SerialLookupOut)
def lookup_serial(
    raw_serial: str,
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> SerialLookupOut:
    """Everything known about one serial.

    `:path` so a pasted QR URL works as-is — normalise_serial takes the last
    segment, which is what support will paste out of a customer's WhatsApp
    message nine times out of ten.
    """
    serial = normalise_serial(raw_serial)
    if not serial:
        raise AppError("invalid_serial", 400, "No serial supplied")

    unit = _unit_out(db, serial)

    allocation_rows = db.execute(
        allocation_select()
        .where(Allocation.serial == serial)
        .order_by(Allocation.allocated_at.desc())
    ).all()
    allocations = [to_allocation_out(row) for row in allocation_rows]
    current_allocation = next(
        (a for a in allocations if a.status in ("allocated", "registered")), None
    )

    warranty_rows = db.execute(
        warranty_select()
        .where(Warranty.serial == serial)
        .order_by(Warranty.registered_at.desc())
    ).all()
    warranties = [to_warranty_item(w, c, d) for w, c, d in warranty_rows]

    live = next((row for row in warranty_rows if row[0].status in LIVE_STATUSES), None)
    current = build_warranty_detail(db, live[0], live[1], live[2]) if live else None

    warranty_ids = [row[0].id for row in warranty_rows]
    claims = _claims_for(db, warranty_ids)
    messages = _messages_for(db, warranty_ids)
    events = _events_for(db, warranty_ids)

    return SerialLookupOut(
        serial=serial,
        unit=unit,
        allocation=current_allocation,
        allocation_history=allocations,
        current_warranty=current,
        warranties=warranties,
        claims=claims,
        sms=messages,
        events=events,
    )


def _claims_for(db: Session, warranty_ids: list[uuid.UUID]) -> list[ClaimListItem]:
    if not warranty_ids:
        return []
    rows = db.execute(
        claim_select()
        .where(Claim.warranty_id.in_(warranty_ids))
        .order_by(Claim.created_at.desc())
    ).all()
    return [to_claim_item(*row) for row in rows]


def _messages_for(db: Session, warranty_ids: list[uuid.UUID]) -> list[SmsOut]:
    if not warranty_ids:
        return []
    messages = db.execute(
        select(SmsMessage)
        .where(SmsMessage.warranty_id.in_(warranty_ids))
        .order_by(SmsMessage.created_at.desc())
    ).scalars()
    return [to_sms_out(m) for m in messages]


def _events_for(db: Session, warranty_ids: list[uuid.UUID]) -> list[WarrantyEventOut]:
    """One merged timeline across every warranty the serial has ever carried.

    Merged deliberately: 'registered, voided, re-registered by another dealer' is
    a single story, and splitting it per warranty hides the sequence that
    matters most in a dispute.
    """
    if not warranty_ids:
        return []
    events = list(
        db.execute(
            select(WarrantyEvent)
            .where(WarrantyEvent.warranty_id.in_(warranty_ids))
            .order_by(WarrantyEvent.created_at.desc())
        ).scalars()
    )
    names = resolve_actor_names(db, {e.actor_id for e in events if e.actor_id})
    return [
        WarrantyEventOut(
            id=event.id,
            warranty_id=event.warranty_id,
            event=event.event,
            from_status=event.from_status,
            to_status=event.to_status,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            actor_name=names.get(event.actor_id) if event.actor_id else None,
            reason=event.reason,
            metadata=event.event_metadata,
            created_at=event.created_at,
        )
        for event in events
    ]
