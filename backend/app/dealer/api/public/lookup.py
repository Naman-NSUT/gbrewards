"""Public warranty lookup — the first screen of the customer support site.

Mount: `api_router.include_router(lookup.router, prefix="/public")`.

Two searches with deliberately different reach:

  * BY MOBILE returns every warranty registered against that number. The caller
    supplied the number, so the result set tells them nothing they did not
    already assert.
  * BY SERIAL returns at most one record, and only in redacted form. A serial is
    not a secret — it is printed on a label in a shop — so anyone who
    photographs one must not thereby learn the buyer's name, number or address.

Both are masked identically. Unmasking the mobile search would make this a
name-harvesting endpoint: type ten thousand numbers, collect ten thousand names.
The support desk works from the admin panel, where the record is not redacted
and every read is behind a login.

POST rather than GET, for both: a mobile number in a query string ends up in
access logs, browser history and any proxy in between.
"""

import uuid

import redis as redis_lib
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import client_ip, get_db, get_redis
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer
from app.dealer.models.warranty import LIVE_STATUSES, Warranty
from app.dealer.schemas.public import LookupIn, LookupOut, RedactedWarrantyOut, redact
from app.dealer.services import ratelimit
from app.dealer.services.unitsource import normalise_serial

router = APIRouter(tags=["public"])

_MAX_RESULTS = 20

# Shown whenever a search comes back empty — including for a serial we have never
# heard of. Identical copy in both cases, so the message is not an oracle for
# "this serial exists but has no warranty".
_EMPTY_MESSAGE = (
    "We could not find a warranty with those details. If your mattress was not "
    "registered at the time of purchase, you can register it yourself with a photo "
    "of your invoice."
)


def _dealers_by_id(db: Session, warranties: list[Warranty]) -> dict[uuid.UUID, Dealer]:
    """One query for the shop names, rather than one per row."""
    ids = {w.dealer_id for w in warranties if w.dealer_id}
    if not ids:
        return {}
    rows = db.execute(select(Dealer).where(Dealer.id.in_(ids))).scalars()
    return {dealer.id: dealer for dealer in rows}


def _by_phone(db: Session, phone: str) -> list[Warranty]:
    customer = db.execute(select(Customer).where(Customer.phone == phone)).scalar_one_or_none()
    if customer is None:
        return []
    stmt = (
        select(Warranty)
        .where(Warranty.customer_id == customer.id)
        .order_by(Warranty.registered_at.desc())
        .limit(_MAX_RESULTS)
    )
    return list(db.execute(stmt).scalars())


def _by_reference(db: Session, raw: str) -> list[Warranty]:
    """Find one warranty by the reference a customer actually has.

    That is a SERIAL for anything bought before registration moved to product +
    invoice, and an INVOICE NUMBER for everything since — those rows have no
    serial at all. Matching only serials would tell a recent customer their
    warranty does not exist.

    The serial is normalised (the printed form has dashes and case); the invoice
    is compared case-insensitively, matching the uniqueness index that issued it.
    """
    typed = (raw or "").strip()
    if not typed:
        return []
    serial = normalise_serial(typed)
    matches = or_(
        Warranty.serial == serial,
        func.lower(Warranty.invoice_ref) == typed.lower(),
    )
    live = db.execute(
        select(Warranty).where(matches, Warranty.status.in_(LIVE_STATUSES)).limit(1)
    ).scalar_one_or_none()
    if live is not None:
        return [live]
    # No live warranty: fall back to the most recent voided one. A customer whose
    # warranty was cancelled deserves to see that it was, rather than being told
    # nothing exists and re-registering it.
    voided = db.execute(
        select(Warranty).where(matches).order_by(Warranty.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    return [voided] if voided is not None else []


@router.post("/lookup", response_model=LookupOut)
def lookup(
    body: LookupIn,
    request: Request,
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
) -> LookupOut:
    # Fail CLOSED. This endpoint answers questions about other people's
    # purchases; if we cannot count requests, we do not answer them. The cost of
    # a Redis outage here is a support site that says "try again shortly"; the
    # cost of failing open is an unmetered enumeration endpoint.
    ratelimit.enforce(
        redis,
        f"public:lookup:{client_ip(request)}",
        limit=settings.public_lookup_per_min_per_ip,
        window_s=60,
        fail_open=False,
    )

    warranties = _by_phone(db, body.phone) if body.phone else _by_reference(db, body.serial or "")

    if not warranties:
        # Not a 404: "we found nothing" is a normal answer on a support site, and
        # a 404 would also let a caller distinguish an unknown serial from a
        # known one by status code alone.
        return LookupOut(results=[], message=_EMPTY_MESSAGE, can_self_register=True)

    dealers = _dealers_by_id(db, warranties)
    results: list[RedactedWarrantyOut] = [
        redact(w, dealer=dealers.get(w.dealer_id) if w.dealer_id else None) for w in warranties
    ]
    return LookupOut(results=results, message=None, can_self_register=False)
