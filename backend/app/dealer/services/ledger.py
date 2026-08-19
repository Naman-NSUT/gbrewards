"""Single source of truth for point math.

Balances are DERIVED. There is no counter column anywhere, so there is nothing
that can disagree with the history that produced it.

    balance   = SUM(ledger_entries.amount) for the dealer
    pending   = SUM(redemptions.points) where status = 'pending'
    available = balance - pending

A pending redemption is itself the hold, so rejecting one releases the hold by
ceasing to be pending — there is no compensating entry to forget to write.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.point_rate import PointRate
from app.dealer.models.reward import Redemption

# Mirrors the CHECK constraint in migration 0001.
REGISTRATION_CREDIT = "registration_credit"
REGISTRATION_REVERSAL = "registration_reversal"
REDEMPTION_DEBIT = "redemption_debit"
REDEMPTION_RELEASE = "redemption_release"
ADMIN_CREDIT = "admin_credit"
ADMIN_DEBIT = "admin_debit"

_ADJUSTMENTS = {ADMIN_CREDIT, ADMIN_DEBIT}


def balance(session: Session, dealer_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.dealer_id == dealer_id
    )
    return int(session.execute(stmt).scalar_one())


def pending(session: Session, dealer_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(Redemption.points), 0)).where(
        Redemption.dealer_id == dealer_id,
        Redemption.status == "pending",
    )
    return int(session.execute(stmt).scalar_one())


def available(session: Session, dealer_id: uuid.UUID) -> int:
    return balance(session, dealer_id) - pending(session, dealer_id)


def total_earned(session: Session, dealer_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.dealer_id == dealer_id, LedgerEntry.amount > 0
    )
    return int(session.execute(stmt).scalar_one())


def current_rate(session: Session, *, product_id: uuid.UUID) -> PointRate | None:
    """The rate in force FOR A PRODUCT.

    At most one row per product can have effective_to IS NULL — the database
    enforces it — so this cannot silently return an arbitrary pick. Returns None
    when the product has no rate configured yet, which credits nothing rather
    than guessing a value; the registration still records, which is the point.
    """
    return session.execute(
        select(PointRate).where(
            PointRate.product_id == product_id, PointRate.effective_to.is_(None)
        )
    ).scalar_one_or_none()


def set_rate(
    session: Session,
    *,
    product_id: uuid.UUID,
    points_per_registration: int,
    admin_id: uuid.UUID | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> PointRate:
    """Change what a registration is worth.

    Closes the current rate and opens a new one, rather than editing a value in
    place. Ledger rows keep pointing at the version that produced them, so
    "why is this row 50 when the rate is 75?" stays answerable after the change.

    The row lock serialises two admins changing the rate at the same moment;
    without it both would close the same rate and the unique index would reject
    one of them with a confusing error.
    """
    moment = now or datetime.now(UTC)
    current = session.execute(
        select(PointRate)
        .where(PointRate.product_id == product_id, PointRate.effective_to.is_(None))
        .with_for_update()
    ).scalar_one_or_none()

    if current is not None:
        if current.points_per_registration == points_per_registration:
            return current
        current.effective_to = moment
        session.flush()

    rate = PointRate(
        product_id=product_id,
        points_per_registration=points_per_registration,
        effective_from=moment,
        note=note,
        created_by_admin_id=admin_id,
    )
    session.add(rate)
    session.flush()
    return rate


def add_entry(
    session: Session,
    *,
    dealer_id: uuid.UUID,
    amount: int,
    type: str,
    staff_id: uuid.UUID | None = None,
    warranty_id: uuid.UUID | None = None,
    redemption_id: uuid.UUID | None = None,
    rate_version_id: uuid.UUID | None = None,
    admin_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LedgerEntry:
    """Append one entry. Does NOT commit — the caller owns the transaction, so a
    credit is always in the same transaction as the thing it pays for.
    """
    if type in _ADJUSTMENTS and not (reason and reason.strip()):
        # The database also refuses this. Checking here too turns a 500 from an
        # IntegrityError into an honest 400 with a usable message.
        raise AppError("reason_required", 400, "A manual point adjustment requires a reason")
    if amount == 0:
        raise AppError("invalid_amount", 400, "A ledger entry of zero points is meaningless")

    entry = LedgerEntry(
        dealer_id=dealer_id,
        staff_id=staff_id,
        amount=amount,
        type=type,
        warranty_id=warranty_id,
        redemption_id=redemption_id,
        rate_version_id=rate_version_id,
        admin_id=admin_id,
        reason=reason,
        entry_metadata=metadata,
    )
    session.add(entry)
    session.flush()
    return entry
