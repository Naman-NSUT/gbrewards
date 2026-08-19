"""Dashboard aggregates.

Everything here is one round trip and computed in SQL. The dashboard is the
first screen after login, so it must not fan out into a dozen queries — and it
must stay fast once there are hundreds of thousands of warranties.

The framing is deliberate: the headline number is not "registrations" but
"registrations the dealers actually made", with customer self-registrations
shown ALONGSIDE rather than folded in. A self-registration is a sale a shop
failed to record; adding it to the same total would hide the problem this
product exists to expose.
"""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_admin, get_db
from app.dealer.api.admin._common import day_window
from app.dealer.models.claim import Claim
from app.dealer.models.dealer import Dealer
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.warranty import Warranty
from app.dealer.services.warranty_dates import business_today
from app.models.admin import Admin

router = APIRouter(tags=["admin-dashboard"])

_LIVE = ("pending_confirmation", "pending_review", "pending_backdate", "active", "claimed")


@router.get("/dashboard")
def dashboard(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    today = business_today()
    # Half-open bounds in the SELLER's timezone. Truncating registered_at with
    # date() would truncate in UTC, so between 00:00 and 05:30 IST the "today"
    # count reported yesterday's figure — wrong every single night.
    today_start, today_end = day_window(today, today)
    month_start, _ = day_window(today.replace(day=1), today)

    def count_warranties(*conditions: Any) -> int:
        stmt = select(func.count()).select_from(Warranty).where(*conditions)
        return int(db.execute(stmt).scalar_one())

    dealer_made = Warranty.source == "dealer"
    self_made = Warranty.source == "customer_self"
    live = Warranty.status.in_(_LIVE)

    points_issued = int(
        db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.amount > 0
            )
        ).scalar_one()
    )
    points_reversed = int(
        db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.type == "registration_reversal"
            )
        ).scalar_one()
    )

    return {
        "today": today.isoformat(),
        "registered_today": count_warranties(
            live,
            dealer_made,
            Warranty.registered_at >= today_start,
            Warranty.registered_at < today_end,
        ),
        "registered_this_month": count_warranties(
            live, dealer_made, Warranty.registered_at >= month_start
        ),
        "self_registered_this_month": count_warranties(
            self_made, Warranty.registered_at >= month_start
        ),
        "active_warranties": count_warranties(Warranty.status == "active"),
        "active_dealers": int(
            db.execute(
                select(func.count()).select_from(Dealer).where(Dealer.status == "active")
            ).scalar_one()
        ),
        "pending_approvals": count_warranties(
            Warranty.status.in_(("pending_backdate", "pending_review"))
        ),
        "open_claims": int(
            db.execute(
                select(func.count())
                .select_from(Claim)
                .where(Claim.status.in_(("open", "in_review")))
            ).scalar_one()
        ),
        "unverified_units": count_warranties(live, Warranty.unit_unverified.is_(True)),
        "points_issued": points_issued,
        # Negative number; shown separately so a healthy programme and one with
        # heavy clawbacks do not look identical.
        "points_reversed": points_reversed,
    }


@router.get("/dashboard/analytics")
def analytics(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Registrations per day, split by who did the recording.

    Dealer and self-registrations are returned as separate series on purpose:
    stacked in the UI, the self-registration band reads as "sales the shops
    didn't record", which is the single most useful picture in the product.
    """
    today = business_today()
    start: date = today - timedelta(days=days - 1)
    window_start, window_end = day_window(start, today)

    # Bucket by the date the sale happened WHERE IT HAPPENED. Grouping on the
    # UTC date would shift every evening sale in India into the next day's bar.
    day = func.date(
        func.timezone(settings.business_timezone, Warranty.registered_at)
    ).label("day")
    rows = db.execute(
        select(day, Warranty.source, func.count().label("n"))
        .where(
            Warranty.registered_at >= window_start,
            Warranty.registered_at < window_end,
            Warranty.status.in_(_LIVE),
        )
        .group_by(day, Warranty.source)
        .order_by(day)
    ).all()

    # str | int because each bucket carries its own date alongside the counts,
    # which is what the chart component consumes directly.
    buckets: dict[str, dict[str, str | int]] = {}
    for offset in range(days):
        key = (start + timedelta(days=offset)).isoformat()
        buckets[key] = {"date": key, "dealer": 0, "customer_self": 0}

    for row_day, source, n in rows:
        key = row_day.isoformat() if hasattr(row_day, "isoformat") else str(row_day)
        if key not in buckets:  # a row outside the window; ignore rather than crash
            continue
        if source == "customer_self":
            buckets[key]["customer_self"] = int(n)
        elif source == "dealer":
            buckets[key]["dealer"] = int(n)

    return {"days": days, "series": list(buckets.values())}


@router.get("/me")
def me(admin: Admin = Depends(get_current_admin)) -> dict[str, Any]:
    return {
        "id": str(admin.id),
        "email": admin.email,
        "name": admin.name,
        "role": admin.role,
    }
