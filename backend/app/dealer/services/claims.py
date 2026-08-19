"""Warranty claims raised from the public support site.

THE GATE: a claim may only be raised by someone who can name BOTH the serial and
the mobile number on the record. A serial alone is not a secret — it is printed
on a label, in a shop, on a mattress anyone can photograph — so serial-only
claims would let a passer-by open a warranty claim against someone else's
purchase, and a competitor open a thousand. The pair is the possession check the
system already has available at zero friction, because the customer received an
SMS on that number when the warranty was registered.

Failure is deliberately INDISTINGUISHABLE: a wrong serial, an unknown serial and
a serial whose registered number does not match all return the same message. Any
difference between them turns this endpoint into an oracle for "does this serial
exist" or "is this the number that bought it".

The public reference is generated, never sequential: a customer reads it out over
the phone, so it excludes O/0 and I/1, and it leaks no volume information about
how many claims the brand receives.
"""

import secrets
import uuid
from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.claim import Claim
from app.dealer.models.warranty import LIVE_STATUSES, Warranty, WarrantyEvent
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.unitsource import normalise_serial

# No O/0 and no I/1: this reference is read aloud and written down by hand.
_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_REFERENCE_LENGTH = 8
_REFERENCE_TRIES = 5

# A claim in one of these states is still being worked; a second submission for
# the same warranty is the same customer chasing it, not a new problem.
OPEN_CLAIM_STATUSES = ("open", "in_review")

# States where the record is not yet a settled fact, so nothing can be claimed
# against it.
_UNSETTLED_STATUSES = ("pending_review", "pending_backdate", "pending_confirmation")


@dataclass
class ClaimSubmission:
    claim: Claim
    warranty: Warranty
    # True when an open claim already existed and was returned instead of a new
    # one being created.
    duplicate: bool


def _no_match() -> NoReturn:
    """One answer for every way of failing to identify a warranty."""
    raise AppError(
        "not_found",
        404,
        "We could not find a warranty with that serial number and mobile number. "
        "Check both, or register your warranty if it was never registered for you.",
    )


def generate_reference(session: Session) -> str:
    """A short, unguessable public reference.

    40 bits of entropy over an unambiguous alphabet. The uniqueness constraint on
    the column is the real guarantee; this loop just avoids surfacing a collision
    to a customer as an error.
    """
    for _ in range(_REFERENCE_TRIES):
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(_REFERENCE_LENGTH))
        taken = session.execute(select(Claim.id).where(Claim.reference == candidate)).first()
        if taken is None:
            return candidate
    raise AppError(  # pragma: no cover - requires five collisions in 32^8
        "reference_unavailable", 503, "Could not open a claim right now, please retry"
    )


def normalise_reference(raw: str) -> str:
    """Accept what a human types: lower case, spaces, dashes."""
    return "".join(ch for ch in (raw or "").upper() if ch in _ALPHABET)


def _warranty_for(session: Session, serial: str) -> Warranty | None:
    """The warranty that matters for this serial: the live one, else the newest."""
    rows = list(
        session.execute(
            select(Warranty).where(Warranty.serial == serial).order_by(Warranty.created_at.desc())
        ).scalars()
    )
    if not rows:
        return None
    return next((w for w in rows if w.status in LIVE_STATUSES), rows[0])


def _assert_claimable(warranty: Warranty) -> None:
    if warranty.status == "voided":
        raise AppError(
            "warranty_voided",
            409,
            "This warranty was cancelled and cannot be claimed against. "
            "Contact GoodBed support if you believe that is wrong.",
        )
    if warranty.status in _UNSETTLED_STATUSES:
        raise AppError(
            "warranty_not_active",
            409,
            "This warranty is still being verified by our team. "
            "You can raise a claim once it is approved.",
        )
    # Expiry is derived, and checked here for every status — a warranty already
    # moved to 'claimed' by an earlier claim can still run out of time.
    if warranty_svc.is_expired(warranty):
        raise AppError(
            "warranty_expired",
            409,
            f"This warranty ended on {warranty.warranty_end_date.strftime('%d-%m-%Y')} "
            "and can no longer be claimed against.",
        )


def open_claim_for(session: Session, warranty_id: uuid.UUID) -> Claim | None:
    return (
        session.execute(
            select(Claim)
            .where(Claim.warranty_id == warranty_id, Claim.status.in_(OPEN_CLAIM_STATUSES))
            .order_by(Claim.created_at.desc())
        )
        .scalars()
        .first()
    )


def submit(
    session: Session,
    *,
    raw_serial: str,
    phone: str,
    description: str,
    issue_type: str | None = None,
    ip: str | None = None,
) -> ClaimSubmission:
    """Raise a claim against a warranty. Caller owns the transaction."""
    serial = normalise_serial(raw_serial)
    if not serial:
        _no_match()

    warranty = _warranty_for(session, serial)
    # Identity check and existence check produce the same outcome on purpose.
    if warranty is None or warranty.customer.phone != phone:
        _no_match()

    _assert_claimable(warranty)

    existing = open_claim_for(session, warranty.id)
    if existing is not None:
        # Chasing an open claim must not create a second one: duplicates split
        # the history of one fault across two references and double the queue.
        return ClaimSubmission(claim=existing, warranty=warranty, duplicate=True)

    claim = Claim(
        reference=generate_reference(session),
        warranty_id=warranty.id,
        customer_id=warranty.customer_id,
        issue_type=issue_type,
        description=description,
        status="open",
    )
    session.add(claim)
    try:
        session.flush()
    except IntegrityError as exc:  # pragma: no cover - reference collision
        session.rollback()
        raise AppError(
            "reference_unavailable", 503, "Could not open a claim right now, please retry"
        ) from exc

    previous = warranty.status
    warranty.status = "claimed"
    session.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event="claim_raised",
            from_status=previous,
            to_status="claimed",
            actor_type="customer",
            actor_id=warranty.customer_id,
            event_metadata={
                "claim_id": str(claim.id),
                "reference": claim.reference,
                "issue_type": issue_type,
                "ip": ip,
            },
        )
    )
    session.flush()

    return ClaimSubmission(claim=claim, warranty=warranty, duplicate=False)


def find_for_status(session: Session, *, reference: str, phone: str) -> tuple[Claim, Warranty]:
    """Look up a claim for the public status page.

    Reference AND mobile, for the same reason submission needs both: a reference
    can be overheard, screenshotted or forwarded, and on its own it must not
    reveal a customer's warranty.
    """
    normalised = normalise_reference(reference)
    claim = (
        session.execute(select(Claim).where(Claim.reference == normalised)).scalar_one_or_none()
        if normalised
        else None
    )
    warranty = session.get(Warranty, claim.warranty_id) if claim else None
    if claim is None or warranty is None or warranty.customer.phone != phone:
        raise AppError(
            "not_found",
            404,
            "We could not find a claim with that reference and mobile number.",
        )
    return claim, warranty
