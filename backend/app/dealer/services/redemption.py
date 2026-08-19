"""Spending points: the hold model, and the two places it can lose money.

    balance   = SUM(ledger_entries.amount)
    pending   = SUM(redemptions.points) WHERE status = 'pending'
    available = balance - pending

A pending request IS the hold. Nothing reaches the ledger until an admin
approves, which buys two things worth more than a "held_points" column:

  * releasing a hold is just leaving `pending` — a rejection or a cancellation
    has no compensating entry anyone can forget to write, and no crash window in
    which points stay held forever;
  * the ledger keeps meaning "points that moved", not "points someone intended
    to move". A dealer reading their statement sees real movements only.

Two moments can overspend, and both take the same lock on the DEALER row:

  * requesting — two taps, or two staff on two phones, each seeing the same
    balance and each committing it;
  * approving — a clawback for a voided registration landing between request and
    approval, so the balance that covered the request no longer does.

The lock is on `dealers` rather than on the ledger because the ledger is
append-only: there is no row to lock, and SELECT FOR UPDATE cannot lock the
absence of rows that a concurrent INSERT is about to create. One row per
dealership, held for the length of one short transaction, serialises exactly the
dealership whose money is at stake and nobody else's.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.reward import Redemption, Reward
from app.dealer.services import ledger
from app.dealer.services.audit import record_audit

# Statuses a redemption can be filtered by. Mirrors the CHECK in migration 0001.
STATUSES = ("pending", "approved", "rejected", "fulfilled", "cancelled")


@dataclass(frozen=True)
class CatalogueEntry:
    reward: Reward
    affordable: bool
    in_stock: bool
    short_by: int


@dataclass(frozen=True)
class Catalogue:
    balance: int
    pending: int
    available: int
    entries: list[CatalogueEntry]


def _lock_dealer(session: Session, dealer_id: uuid.UUID) -> Dealer:
    """Serialise every balance-spending decision for one dealership.

    Taken BEFORE reading the balance, never after: a check on an unlocked read
    is a check on a number that another transaction is already changing.
    """
    dealer = session.execute(
        select(Dealer).where(Dealer.id == dealer_id).with_for_update()
    ).scalar_one_or_none()
    if dealer is None:
        raise AppError("dealer_not_found", 404, "Unknown dealership")
    return dealer


def _holds_excluding(session: Session, *, dealer_id: uuid.UUID, redemption_id: uuid.UUID) -> int:
    """Points held by this dealer's OTHER pending requests.

    A redemption being approved is still `pending` and so still counts toward
    its own hold; subtracting it here is what makes the approval check read as
    "does the balance cover this request", not "does it cover it twice".
    """
    stmt = select(func.coalesce(func.sum(Redemption.points), 0)).where(
        Redemption.dealer_id == dealer_id,
        Redemption.status == "pending",
        Redemption.id != redemption_id,
    )
    return int(session.execute(stmt).scalar_one())


def _append_note(existing: str | None, addition: str) -> str:
    """Keep the dealer's own note when an admin adds a processing note.

    One `note` column, two authors. Overwriting would delete the dealer's
    "please send to the Andheri branch" the moment anyone rejected the request.
    """
    return f"{existing.strip()} | {addition}" if existing and existing.strip() else addition


def catalogue(session: Session, *, dealer_id: uuid.UUID) -> Catalogue:
    """The active catalogue, priced against what this dealer can actually spend."""
    balance = ledger.balance(session, dealer_id)
    held = ledger.pending(session, dealer_id)
    available = balance - held

    rewards = list(
        session.execute(
            select(Reward)
            .where(Reward.is_active.is_(True))
            .order_by(Reward.sort_order, Reward.points_cost, Reward.name)
        ).scalars()
    )
    entries = [
        CatalogueEntry(
            reward=reward,
            affordable=reward.points_cost <= available,
            # Separate from `affordable` on purpose: "you need 200 more points"
            # and "we have run out" are different problems for the dealer.
            in_stock=reward.stock is None or reward.stock > 0,
            short_by=max(0, reward.points_cost - available),
        )
        for reward in rewards
    ]
    return Catalogue(balance=balance, pending=held, available=available, entries=entries)


def get_for_dealer(
    session: Session, *, redemption_id: uuid.UUID, dealer_id: uuid.UUID
) -> Redemption:
    """Fetch a redemption scoped to one dealership.

    404 rather than 403 for another dealership's request: a staff member has no
    business learning that a given id exists at all.
    """
    redemption = session.get(Redemption, redemption_id)
    if redemption is None or redemption.dealer_id != dealer_id:
        raise AppError("not_found", 404, "No such redemption request")
    return redemption


def history(
    session: Session,
    *,
    dealer_id: uuid.UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Redemption], int]:
    if status is not None and status not in STATUSES:
        raise AppError("invalid_status", 400, f"Unknown status '{status}'")

    filters = [Redemption.dealer_id == dealer_id]
    if status is not None:
        filters.append(Redemption.status == status)

    total = int(
        session.execute(select(func.count()).select_from(Redemption).where(*filters)).scalar_one()
    )
    rows = list(
        session.execute(
            select(Redemption)
            .where(*filters)
            # id as a tiebreaker: two requests can share a created_at to the
            # microsecond, and an unstable sort silently duplicates or drops a
            # row across pages.
            .order_by(Redemption.created_at.desc(), Redemption.id.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    return rows, total


def create(
    session: Session,
    *,
    staff: DealerStaff,
    reward_id: uuid.UUID,
    note: str | None = None,
) -> Redemption:
    """Request a reward. Places the hold; writes no ledger row. Caller commits."""
    dealer = _lock_dealer(session, staff.dealer_id)
    if dealer.status != "active":
        raise AppError("dealer_inactive", 403, "This dealership is not active")

    reward = session.get(Reward, reward_id)
    if reward is None or not reward.is_active:
        raise AppError("reward_unavailable", 404, "This reward is not available")
    if reward.stock is not None and reward.stock <= 0:
        raise AppError("out_of_stock", 409, f"{reward.name} is out of stock")

    available = ledger.available(session, dealer.id)
    if reward.points_cost > available:
        raise AppError(
            "insufficient_points",
            409,
            "Not enough available points for this reward",
            {
                "available": available,
                "required": reward.points_cost,
                "short_by": reward.points_cost - available,
            },
        )

    redemption = Redemption(
        dealer_id=dealer.id,
        # Attribution only. The points, and the reward, belong to the shop.
        requested_by_staff_id=staff.id,
        reward_id=reward.id,
        # Price and name are COPIED, not referenced. A catalogue edit tomorrow
        # must not silently reprice a request already in the queue — in either
        # direction, and least of all upward after the dealer has committed.
        points=reward.points_cost,
        reward_name=reward.name,
        status="pending",
        note=note,
    )
    session.add(redemption)
    session.flush()
    return redemption


def approve(
    session: Session,
    *,
    redemption: Redemption,
    admin_id: uuid.UUID,
    note: str | None = None,
) -> Redemption:
    """Approve a pending request: debit the ledger, take the stock. Caller commits.

    This is the function the admin endpoint calls. The re-check below is the
    whole point of it: between the request and this moment a registration may
    have been voided and clawed back, and paying out of a balance that no longer
    exists is how a dealer registers fake sales, redeems fast and leaves the
    brand holding the loss.
    """
    if redemption.status != "pending":
        raise AppError("not_pending", 409, f"This request has already been {redemption.status}")

    _lock_dealer(session, redemption.dealer_id)
    balance = ledger.balance(session, redemption.dealer_id)
    other_holds = _holds_excluding(
        session, dealer_id=redemption.dealer_id, redemption_id=redemption.id
    )
    spendable = balance - other_holds
    if spendable < redemption.points:
        raise AppError(
            "insufficient_points",
            409,
            "This dealer's balance no longer covers the request",
            {
                "balance": balance,
                "other_holds": other_holds,
                "required": redemption.points,
            },
        )

    if redemption.reward_id is not None:
        # Locked because stock is a counter, not a derived value — two admins
        # approving the last unit at once would otherwise both see 1.
        reward = session.execute(
            select(Reward).where(Reward.id == redemption.reward_id).with_for_update()
        ).scalar_one_or_none()
        if reward is not None and reward.stock is not None:
            if reward.stock <= 0:
                raise AppError("out_of_stock", 409, f"{reward.name} is out of stock")
            reward.stock -= 1

    # The one ledger row this whole flow produces. uq_ledger_redemption_debit
    # makes a second one physically impossible even if this code is wrong.
    ledger.add_entry(
        session,
        dealer_id=redemption.dealer_id,
        staff_id=redemption.requested_by_staff_id,
        amount=-redemption.points,
        type=ledger.REDEMPTION_DEBIT,
        redemption_id=redemption.id,
        admin_id=admin_id,
        reason=note,
        metadata={"reward": redemption.reward_name},
    )

    redemption.status = "approved"
    redemption.processed_by_admin_id = admin_id
    redemption.processed_at = datetime.now(UTC)
    if note and note.strip():
        redemption.note = _append_note(redemption.note, note.strip())

    record_audit(
        session,
        action="approve_redemption",
        entity_type="redemption",
        entity_id=redemption.id,
        actor_id=admin_id,
        reason=note,
        metadata={
            "dealer_id": str(redemption.dealer_id),
            "points": redemption.points,
            "reward": redemption.reward_name,
        },
    )
    session.flush()
    return redemption


def reject(
    session: Session,
    *,
    redemption: Redemption,
    admin_id: uuid.UUID,
    reason: str,
) -> Redemption:
    """Refuse a pending request. Releases the hold; writes no ledger row.

    A reason is mandatory. The dealer earned these points and is being told no —
    "rejected" with no explanation is how a rewards programme loses the dealers
    it was built to motivate.
    """
    if not (reason and reason.strip()):
        raise AppError("reason_required", 400, "Rejecting a redemption requires a reason")
    if redemption.status != "pending":
        raise AppError("not_pending", 409, f"This request has already been {redemption.status}")

    redemption.status = "rejected"
    redemption.processed_by_admin_id = admin_id
    redemption.processed_at = datetime.now(UTC)
    redemption.note = _append_note(redemption.note, f"Rejected: {reason.strip()}")

    record_audit(
        session,
        action="reject_redemption",
        entity_type="redemption",
        entity_id=redemption.id,
        actor_id=admin_id,
        reason=reason,
        metadata={
            "dealer_id": str(redemption.dealer_id),
            "points": redemption.points,
            "reward": redemption.reward_name,
        },
    )
    session.flush()
    return redemption


def cancel(session: Session, *, redemption: Redemption, staff: DealerStaff) -> Redemption:
    """Dealer withdraws their own pending request. Releases the hold.

    Scoping is re-checked here and not only at the router: this function moves
    points, so it does not assume the caller looked the row up correctly.
    """
    if redemption.dealer_id != staff.dealer_id:
        raise AppError("not_found", 404, "No such redemption request")
    if redemption.status != "pending":
        raise AppError("not_pending", 409, f"This request has already been {redemption.status}")

    redemption.status = "cancelled"
    # Not an admin action, so processed_by_admin_id stays null — but the row did
    # leave the queue at a moment worth recording.
    redemption.processed_at = datetime.now(UTC)

    record_audit(
        session,
        action="cancel_redemption",
        entity_type="redemption",
        entity_id=redemption.id,
        actor_type="dealer_staff",
        actor_id=staff.id,
        actor_label=staff.phone,
        metadata={"points": redemption.points, "reward": redemption.reward_name},
    )
    session.flush()
    return redemption
