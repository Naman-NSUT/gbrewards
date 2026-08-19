"""The dealer's own account: who I am, what my shop has earned, and why.

The ledger endpoint is the reason this file matters. A points programme the
dealer cannot audit is a programme they stop trusting the first time a number
looks wrong, and "trust the number" is what makes them keep scanning — which is
the sale record, which is the product. So every row is labelled in words and
carries the serial it came from.
"""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_staff, get_db
from app.core.errors import AppError
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.reward import Redemption
from app.dealer.models.warranty import Warranty
from app.dealer.schemas.rewards import (
    DealerBrief,
    LedgerEntryOut,
    LedgerPage,
    PointsOut,
    ProfileOut,
    ProfileUpdateIn,
    StaffOut,
    entry_label,
)
from app.dealer.services import ledger
from app.dealer.services.audit import record_audit
from app.dealer.services.warranty_dates import business_today

router = APIRouter(tags=["dealer-profile"])


def _month_start(now: datetime | None = None) -> datetime:
    """First instant of the current month in the seller's timezone.

    Not UTC: on the 1st, an Indian shop would otherwise be told it had zero
    registrations this month until 05:30, and see last month's total before it.
    """
    today = business_today(now)
    return datetime(today.year, today.month, 1, tzinfo=ZoneInfo(settings.business_timezone))


def _registrations_this_month(session: Session, dealer_id: uuid.UUID) -> int:
    """Live registrations booked this month.

    Voided ones are excluded: a returned mattress paid nothing and is not
    compliance the dealer should be shown credit for.
    """
    stmt = (
        select(func.count())
        .select_from(Warranty)
        .where(
            Warranty.dealer_id == dealer_id,
            Warranty.registered_at >= _month_start(),
            Warranty.status != "voided",
        )
    )
    return int(session.execute(stmt).scalar_one())


@router.get("/me", response_model=ProfileOut)
def my_profile(
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> ProfileOut:
    dealer = db.get(Dealer, staff.dealer_id)
    if dealer is None:  # pragma: no cover - get_current_staff already proved it exists
        raise AppError("dealer_not_found", 404, "Unknown dealership")

    return ProfileOut(
        staff=StaffOut.model_validate(staff),
        dealer=DealerBrief.model_validate(dealer),
        points=PointsOut(
            balance=ledger.balance(db, staff.dealer_id),
            pending=ledger.pending(db, staff.dealer_id),
            available=ledger.available(db, staff.dealer_id),
            total_earned=ledger.total_earned(db, staff.dealer_id),
        ),
        registrations_this_month=_registrations_this_month(db, staff.dealer_id),
    )


@router.patch("/me", response_model=StaffOut)
def update_my_profile(
    body: ProfileUpdateIn,
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> StaffOut:
    """Correct my own name. Nothing else.

    Not the phone number: it is the login identity, so self-service changes are
    an account takeover in one PATCH. Not the role, not the dealership, not
    another staff member — those are admin provisioning decisions, and this
    endpoint only ever addresses `me`, so there is no id to tamper with.

    The change is audited because the name is the attribution label printed
    against every registration this person made.
    """
    previous = staff.name
    if body.name == previous:
        return StaffOut.model_validate(staff)

    staff.name = body.name
    record_audit(
        db,
        action="edit_staff_name",
        entity_type="dealer_staff",
        entity_id=staff.id,
        actor_type="dealer_staff",
        actor_id=staff.id,
        actor_label=staff.phone,
        metadata={"from": previous, "to": body.name},
    )
    out = StaffOut.model_validate(staff)
    db.commit()
    return out


@router.get("/ledger", response_model=LedgerPage)
def my_ledger(
    staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LedgerPage:
    total = int(
        db.execute(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.dealer_id == staff.dealer_id)
        ).scalar_one()
    )

    # The serial and the reward name are joined in rather than fetched per row:
    # a statement screen is the one place in this app that reads many rows at
    # once, and N+1 on it is felt on a shop-floor connection.
    rows = db.execute(
        select(LedgerEntry, Warranty.serial, Redemption.reward_name)
        .outerjoin(Warranty, LedgerEntry.warranty_id == Warranty.id)
        .outerjoin(Redemption, LedgerEntry.redemption_id == Redemption.id)
        .where(LedgerEntry.dealer_id == staff.dealer_id)
        # id as a tiebreaker: entries written in one transaction can share a
        # created_at, and an unstable sort duplicates or drops rows across pages.
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return LedgerPage(
        total=total,
        limit=limit,
        offset=offset,
        balance=ledger.balance(db, staff.dealer_id),
        items=[
            LedgerEntryOut(
                id=entry.id,
                amount=entry.amount,
                type=entry.type,
                label=entry_label(entry.type),
                serial=serial,
                reward_name=reward_name,
                reason=entry.reason,
                created_at=entry.created_at,
            )
            for entry, serial, reward_name in rows
        ],
    )
