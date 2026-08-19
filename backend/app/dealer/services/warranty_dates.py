"""Warranty clock policy — the one thing this system exists to get right.

The failure this product was built to stop is a warranty whose clock starts when
someone got round to registering it rather than when the mattress was sold. So
the start date is derived from server state, never from a value the dealer types.

    default start        = today, in the seller's timezone, from the server clock
    dealer influence     = an invoice_date may pull the start BACKWARD by at most
                           BACKDATE_GRACE_DAYS (default 7)
    beyond the window    = not rejected, and not silently accepted either —
                           the warranty is created in `pending_backdate` and an
                           admin decides, with the requested date recorded
    future dates         = never honoured; a dealer cannot start a clock late

Why a grace window at all rather than a strict server timestamp: real shops
write the invoice on Saturday and register on Monday, and a system that punishes
that teaches dealers to stop using it. Seven days absorbs a normal weekend and a
public holiday while still making a year-late registration impossible to do
quietly. The window is configurable, and every non-zero backdate is stored on the
warranty and shows on an admin report — so "how often is this being used?" is a
question the client can answer rather than guess.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


@dataclass(frozen=True)
class ClockDecision:
    start_date: date
    end_date: date
    backdate_days: int
    # True when the requested date exceeded the grace window and the warranty
    # must wait for an admin rather than starting now.
    needs_approval: bool
    # The date the dealer asked for, kept even when not honoured, so the approval
    # queue can show what was actually claimed.
    requested_date: date | None


def business_today(now: datetime | None = None) -> date:
    """Today's calendar date where the sale happens.

    Not UTC: a 9pm sale in India is still today's sale, and booking it as
    tomorrow would be visibly wrong to the dealer who made it.
    """
    tz = ZoneInfo(settings.business_timezone)
    moment = now.astimezone(tz) if now else datetime.now(tz)
    return moment.date()


def add_months(start: date, months: int) -> date:
    """Add whole months, clamping to the last valid day.

    31 Jan + 1 month is 28 Feb (or 29th), not 3 March. Getting this wrong shifts
    a warranty end date by days on exactly the dates a customer is most likely to
    dispute it.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    last_day = monthrange(year, month)[1]
    return date(year, month, min(start.day, last_day))


def decide_clock(
    *,
    warranty_months: int,
    invoice_date: date | None,
    now: datetime | None = None,
    grace_days: int | None = None,
    admin_override: bool = False,
) -> ClockDecision:
    """Resolve the warranty window from server state plus a bounded dealer hint.

    `admin_override=True` is used when an admin approves a backdate: the
    requested date is honoured in full, and the caller records who approved it.
    """
    today = business_today(now)
    window = settings.backdate_grace_days if grace_days is None else grace_days

    requested = invoice_date
    start = today
    backdate_days = 0
    needs_approval = False

    if requested is not None:
        # A future invoice date would start the clock LATE — the exact abuse this
        # system exists to prevent — so it contributes nothing. Silently ignored
        # rather than rejected: the dealer probably mistyped, and failing a real
        # sale over a typo helps nobody.
        requested_delta = 0 if requested > today else (today - requested).days

        if requested_delta > 0:
            if admin_override or requested_delta <= window:
                start = requested
                backdate_days = requested_delta
            else:
                # Hold at the requested date but park the warranty for approval,
                # so an approver sees the real claim rather than a normalised one.
                start = requested
                backdate_days = requested_delta
                needs_approval = True

    return ClockDecision(
        start_date=start,
        end_date=add_months(start, warranty_months),
        backdate_days=backdate_days,
        needs_approval=needs_approval,
        requested_date=requested,
    )
