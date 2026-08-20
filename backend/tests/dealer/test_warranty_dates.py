"""The warranty clock, pinned in isolation.

test_registration_abuse.py proves the policy through the registration path. This
file pins the policy function itself — including the calendar cases that only
occur on a handful of dates a year, are impossible to reproduce on demand later,
and shift a warranty end date by days on exactly the dates a customer is most
likely to dispute it.
"""

from datetime import UTC, date, datetime, timedelta

from app.core.config import settings
from app.dealer.services import registration
from app.dealer.services.warranty_dates import add_months, business_today, decide_clock
from tests.dealer.factories import (
    make_dealer,
    make_rate,
    make_staff,
    make_unit,
    new_serial,
)

# A fixed instant to reason from: 11:30 IST on 15 June 2025.
NOW = datetime(2025, 6, 15, 6, 0, tzinfo=UTC)
TODAY = date(2025, 6, 15)


def _clock(invoice_date: date | None, **kw):  # type: ignore[no-untyped-def]
    return decide_clock(warranty_months=60, invoice_date=invoice_date, now=NOW, **kw)


# --- business_today --------------------------------------------------------


def test_business_today_is_the_sellers_calendar_date_not_utc():
    """A 9pm sale in India is today's sale, not tomorrow's and not yesterday's."""
    # 21:00 IST — the same calendar day in UTC too, the easy case.
    assert business_today(datetime(2025, 3, 10, 15, 30, tzinfo=UTC)) == date(2025, 3, 10)
    # 23:30 IST on the 10th: still the 10th for the shop, already the 10th in UTC.
    assert business_today(datetime(2025, 3, 10, 18, 0, tzinfo=UTC)) == date(2025, 3, 10)
    # 05:00 IST on the 11th: the seller's date has rolled over while UTC has not.
    assert business_today(datetime(2025, 3, 10, 23, 30, tzinfo=UTC)) == date(2025, 3, 11)
    # 04:00 IST on the 1st of a month, from the previous UTC day.
    assert business_today(datetime(2025, 2, 28, 22, 30, tzinfo=UTC)) == date(2025, 3, 1)


# --- decide_clock: the default ---------------------------------------------


def test_start_defaults_to_business_today_when_no_invoice_date_is_given():
    decision = _clock(None)

    assert decision.start_date == TODAY
    assert decision.end_date == date(2030, 6, 15)
    assert decision.backdate_days == 0
    assert decision.needs_approval is False
    assert decision.requested_date is None


def test_start_defaults_to_the_real_server_date_when_no_clock_is_injected():
    decision = decide_clock(warranty_months=60, invoice_date=None)

    assert decision.start_date == business_today()
    assert decision.end_date == add_months(business_today(), 60)
    assert decision.backdate_days == 0


# --- decide_clock: the grace window ----------------------------------------


def test_an_invoice_date_inside_the_grace_window_is_honoured_in_full():
    """Saturday's invoice registered on Monday must keep Saturday's clock."""
    for days in range(1, settings.backdate_grace_days + 1):
        requested = TODAY - timedelta(days=days)
        decision = _clock(requested)

        assert decision.start_date == requested, f"{days} days back"
        assert decision.backdate_days == days
        assert decision.needs_approval is False
        assert decision.requested_date == requested
        assert decision.end_date == add_months(requested, 60)


def test_one_day_beyond_the_grace_window_needs_approval():
    days = settings.backdate_grace_days + 1
    requested = TODAY - timedelta(days=days)
    decision = _clock(requested)

    assert decision.needs_approval is True
    assert decision.backdate_days == days
    # The claim is preserved rather than normalised, so the approver sees what
    # the dealer actually asked for.
    assert decision.start_date == requested
    assert decision.requested_date == requested


def test_a_year_late_registration_needs_approval_and_records_the_real_claim():
    """The exact failure this product exists to stop."""
    requested = TODAY - timedelta(days=400)
    decision = _clock(requested)

    assert decision.needs_approval is True
    assert decision.backdate_days == 400
    assert decision.start_date == requested
    assert decision.end_date == add_months(requested, 60)


def test_the_grace_window_is_configurable_per_call():
    one_day_back = TODAY - timedelta(days=1)

    strict = _clock(one_day_back, grace_days=0)
    assert strict.needs_approval is True
    assert strict.backdate_days == 1

    generous = _clock(TODAY - timedelta(days=30), grace_days=30)
    assert generous.needs_approval is False
    assert generous.start_date == TODAY - timedelta(days=30)
    assert generous.backdate_days == 30


def test_todays_invoice_date_is_not_treated_as_a_backdate():
    decision = _clock(TODAY)

    assert decision.start_date == TODAY
    assert decision.backdate_days == 0
    assert decision.needs_approval is False


# --- decide_clock: future dates --------------------------------------------


def test_a_future_invoice_date_never_moves_the_start_forward():
    """A dealer cannot start the clock late — that is the whole abuse."""
    for ahead in (1, 30, 365):
        requested = TODAY + timedelta(days=ahead)
        decision = _clock(requested)

        assert decision.start_date == TODAY, f"{ahead} days ahead"
        assert decision.backdate_days == 0
        assert decision.needs_approval is False, "a typo must not block the sale"
        # Still recorded: a pattern of future dates is worth seeing.
        assert decision.requested_date == requested


def test_admin_override_still_cannot_start_the_clock_late():
    decision = _clock(TODAY + timedelta(days=10), admin_override=True)

    assert decision.start_date == TODAY
    assert decision.backdate_days == 0


# --- decide_clock: admin override ------------------------------------------


def test_admin_override_honours_any_past_date():
    requested = TODAY - timedelta(days=400)
    decision = _clock(requested, admin_override=True)

    assert decision.start_date == requested
    assert decision.backdate_days == 400
    assert decision.needs_approval is False, "the human already approved it"
    assert decision.end_date == add_months(requested, 60)


# --- add_months ------------------------------------------------------------


def test_add_months_clamps_to_the_last_day_of_a_shorter_month():
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29), "leap February"
    assert add_months(date(2024, 3, 31), 1) == date(2024, 4, 30)
    assert add_months(date(2024, 8, 31), 6) == date(2025, 2, 28)
    assert add_months(date(2025, 5, 31), 1) == date(2025, 6, 30)


def test_add_months_handles_leap_years():
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert add_months(date(2024, 2, 29), 48) == date(2028, 2, 29), "lands on a leap year again"
    assert add_months(date(2023, 2, 28), 12) == date(2024, 2, 28)
    assert add_months(date(2024, 2, 28), 12) == date(2025, 2, 28)


def test_add_months_of_sixty_is_exactly_five_years():
    assert add_months(date(2025, 8, 15), 60) == date(2030, 8, 15)
    assert add_months(date(2025, 12, 31), 60) == date(2030, 12, 31)
    assert add_months(date(2024, 2, 29), 60) == date(2029, 2, 28), "no 29th to land on"
    assert add_months(date(2026, 1, 1), 60) == date(2031, 1, 1)


def test_add_months_wraps_months_and_years_correctly():
    assert add_months(date(2025, 12, 31), 1) == date(2026, 1, 31)
    assert add_months(date(2025, 11, 30), 2) == date(2026, 1, 30)
    assert add_months(date(2025, 12, 1), 12) == date(2026, 12, 1)
    assert add_months(date(2025, 1, 1), 24) == date(2027, 1, 1)
    assert add_months(date(2025, 8, 15), 0) == date(2025, 8, 15)


# --- End to end, through a real registration -------------------------------


def test_a_leap_day_sale_stores_a_clamped_five_year_end_date(db):
    """The clamping has to survive the whole path, not just the helper."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    make_rate(db, 50)
    serial = new_serial()
    make_unit(db, serial, months=60)

    leap_day = datetime(2024, 2, 29, 6, 0, tzinfo=UTC)  # 11:30 IST
    result = registration.register(
        db,
        staff=staff,
        raw_serial=serial,
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
        invoice_ref="INV-2024-0229",
        now=leap_day,
    )
    db.commit()

    assert result.warranty.warranty_start_date == date(2024, 2, 29)
    assert result.warranty.warranty_end_date == date(2029, 2, 28)
    assert result.warranty.backdate_days == 0


def test_a_backdated_registration_stores_the_end_date_from_the_backdated_start(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    make_rate(db, 50)
    serial = new_serial()
    make_unit(db, serial, months=60)

    now = datetime(2025, 3, 5, 6, 0, tzinfo=UTC)  # 11:30 IST on 5 March 2025
    result = registration.register(
        db,
        staff=staff,
        raw_serial=serial,
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
        invoice_ref="INV-2025-0301",
        invoice_date=date(2025, 3, 1),
        now=now,
    )
    db.commit()

    assert result.warranty.warranty_start_date == date(2025, 3, 1)
    assert result.warranty.backdate_days == 4
    # Five years from the SALE, not from the day someone got round to typing it.
    assert result.warranty.warranty_end_date == date(2030, 3, 1)
    assert result.warranty.status == "active"
