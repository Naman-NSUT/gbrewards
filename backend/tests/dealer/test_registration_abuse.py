"""The paths that actually matter: abuse and failure, not the happy path.

Each test here corresponds to a way the system could lose money or lose the
truth about when a warranty started.

What a dealer may register, and the one-live-warranty-per-invoice cap that
replaced the serial, live in test_product_registration.py. This file owns what
happens to a registration AFTER it exists — the clock it claims, the approval it
waits for, and the points a void takes back — plus the two facts about serials
that the new flow quietly depends on and that nothing else would notice
breaking.
"""

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.dealer.services import ledger, registration
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.warranty_dates import business_today
from tests.dealer.factories import (
    make_dealer,
    make_priced_product,
    make_product,
    make_staff,
    new_invoice,
)


def _register(db, staff, product, **kw):
    defaults = dict(
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
        invoice_ref=new_invoice(),
    )
    defaults.update(kw)
    result = registration.register(db, staff=staff, product_id=product.id, **defaults)
    db.commit()
    return result


# --- The happy path, once, so the rest has a baseline ----------------------


def test_registration_credits_once_and_starts_clock_today(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)

    result = _register(db, staff, product)

    assert result.points_awarded == 50
    assert result.warranty.status == "active"
    assert result.warranty.warranty_start_date == business_today()
    # 60 months from today, stored explicitly rather than derived at read time.
    assert result.warranty.warranty_end_date.year == business_today().year + 5
    assert result.warranty.warranty_months == 60
    assert ledger.balance(db, dealer.id) == 50


# --- Backdating ------------------------------------------------------------


def test_invoice_date_inside_grace_window_is_honoured(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)

    three_days_ago = business_today() - timedelta(days=3)
    result = _register(db, staff, product, invoice_date=three_days_ago)

    assert result.warranty.status == "active"
    assert result.warranty.warranty_start_date == three_days_ago
    assert result.warranty.backdate_days == 3


def test_backdate_beyond_window_parks_for_approval_and_pays_nothing_yet(db):
    """A year-late registration is the exact failure this product exists to stop."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)

    long_ago = business_today() - timedelta(days=400)
    result = _register(db, staff, product, invoice_date=long_ago)

    assert result.warranty.status == "pending_backdate"
    assert result.warranty.backdate_days == 400
    assert result.points_awarded == 0
    assert ledger.balance(db, dealer.id) == 0, "must not pay before a human approves"


def test_a_warranty_waiting_on_a_human_still_holds_its_invoice_number(db):
    """pending_backdate is a LIVE status, so the invoice is already spoken for.

    If it were not, the cheapest way to be paid twice for one bill would be to
    submit it once with a year-old date — parked, unpaid, and invisible to the
    duplicate check — and then again with today's, which pays immediately.
    """
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)
    invoice = new_invoice()

    _register(
        db, staff, product, invoice_ref=invoice, invoice_date=business_today() - timedelta(days=400)
    )

    with pytest.raises(AppError) as exc:
        _register(db, staff, product, invoice_ref=invoice)
    assert exc.value.code == "duplicate_invoice"
    db.rollback()
    assert ledger.balance(db, dealer.id) == 0


def test_future_invoice_date_cannot_start_the_clock_late(db):
    """The clock is server-authoritative: a dealer cannot push the start forward."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)

    next_year = business_today() + timedelta(days=365)
    result = _register(db, staff, product, invoice_date=next_year)

    assert result.warranty.warranty_start_date == business_today()
    assert result.warranty.backdate_days == 0


def test_approving_a_backdate_activates_and_pays_and_is_audited(db):
    from app.dealer.models.audit_log import DealerAuditLog as AuditLog
    from tests.dealer.factories import make_admin

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    product = make_priced_product(db, 50)

    result = _register(db, staff, product, invoice_date=business_today() - timedelta(days=400))
    points = warranty_svc.approve(
        db, warranty=result.warranty, admin_id=admin.id, reason="Verified paper invoice"
    )
    db.commit()

    assert points == 50
    assert result.warranty.status == "active"
    assert result.warranty.backdate_approved_by_admin_id == admin.id
    assert ledger.balance(db, dealer.id) == 50
    audit = db.query(AuditLog).filter_by(action="approve_backdate").one()
    assert audit.reason == "Verified paper invoice"


# --- Void and clawback -----------------------------------------------------


def test_void_writes_a_compensating_debit_and_never_edits_history(db):
    from app.dealer.models.ledger_entry import LedgerEntry
    from tests.dealer.factories import make_admin

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    product = make_priced_product(db, 50)

    result = _register(db, staff, product)
    clawed = warranty_svc.void(
        db,
        warranty=result.warranty,
        reason="Customer returned the mattress",
        actor_type="admin",
        actor_id=admin.id,
    )
    db.commit()

    assert clawed == 50
    assert ledger.balance(db, dealer.id) == 0
    entries = db.query(LedgerEntry).order_by(LedgerEntry.created_at).all()
    assert len(entries) == 2, "the original credit must still be there"
    assert entries[0].amount == 50 and entries[0].type == "registration_credit"
    assert entries[1].amount == -50 and entries[1].type == "registration_reversal"


def test_clawback_may_drive_the_balance_negative(db):
    """Refusing to claw back from a dealer who already spent the points would
    make fake-register-then-redeem a profitable strategy."""
    from tests.dealer.factories import make_admin

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    product = make_priced_product(db, 50)
    result = _register(db, staff, product)

    # Dealer spends the points before the return comes back.
    ledger.add_entry(
        db,
        dealer_id=dealer.id,
        amount=-50,
        type=ledger.ADMIN_DEBIT,
        admin_id=admin.id,
        reason="redeemed",
    )
    db.commit()

    warranty_svc.void(
        db, warranty=result.warranty, reason="Returned", actor_type="admin", actor_id=admin.id
    )
    db.commit()
    assert ledger.balance(db, dealer.id) == -50


def test_void_requires_a_reason(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)
    result = _register(db, staff, product)

    with pytest.raises(AppError) as exc:
        warranty_svc.void(db, warranty=result.warranty, reason="  ")
    assert exc.value.code == "reason_required"


# --- Unpriced stock --------------------------------------------------------


def test_a_product_with_no_rate_registers_but_pays_nothing(db):
    """Recording the sale is the product; the points are the incentive. An
    unpriced product must never block a registration — it just earns zero until
    someone sets a rate, which the admin compliance screen surfaces."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_product(db)  # real product, no rate configured

    result = _register(db, staff, product)
    assert result.warranty.status == "active"
    assert result.points_awarded == 0
    assert ledger.balance(db, dealer.id) == 0


# --- Serials, after the scanner ---------------------------------------------
#
# Nothing writes a serial any more, but `warranties.serial` and its partial
# unique index are still there, holding up two facts the new flow leans on
# without ever mentioning them. Both are properties of Postgres and of migration
# 0011, so no amount of reading registration.py would reveal either one breaking.


def test_many_live_warranties_may_share_a_null_serial(db):
    """The single fact that made dropping the serial possible at all.

    uq_warranties_live_serial is a unique index on `serial` over live statuses,
    and every registration made since 0011 writes NULL there. Postgres treats
    NULLs as distinct in a unique index, so they do not collide — if it did not,
    the SECOND registration ever made under the new flow would fail on an index
    about a column nobody uses.
    """
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)

    first = _register(db, staff, product, customer_phone="+919812345678")
    second = _register(db, staff, product, customer_phone="+919888888888")

    assert first.warranty.serial is None and second.warranty.serial is None
    assert first.warranty.id != second.warranty.id
    assert ledger.balance(db, dealer.id) == 100


def test_the_database_still_refuses_two_live_warranties_on_one_historic_serial(db):
    """Making `serial` nullable must not have weakened the old guarantee.

    Warranties written before the dropdown still carry the code printed under
    their QR, and each of those mattresses may still hold exactly one live
    warranty. The rule is an index, so it holds whatever the service layer
    believes — which is the only reason it can be trusted for rows no current
    code path writes.
    """
    from tests.dealer.factories import make_legacy_warranty, new_serial

    dealer = make_dealer(db)
    serial = new_serial()
    make_legacy_warranty(db, dealer=dealer, serial=serial)

    with pytest.raises(IntegrityError):
        make_legacy_warranty(db, dealer=dealer, serial=serial, customer_phone="+919888888888")
    db.rollback()
