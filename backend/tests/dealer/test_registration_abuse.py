"""The paths that actually matter: abuse and failure, not the happy path.

Each test here corresponds to a way the system could lose money or lose the
truth about when a warranty started.
"""

import threading
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.dealer.services import ledger, registration
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.warranty_dates import business_today
from tests.dealer.factories import (
    allocate,
    make_dealer,
    make_priced_unit,
    make_staff,
    make_unit,
    new_serial,
)


def _register(db, staff, serial, **kw):
    defaults = dict(
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
        invoice_ref="INV-1001",
    )
    defaults.update(kw)
    result = registration.register(db, staff=staff, raw_serial=serial, **defaults)
    db.commit()
    return result


# --- The happy path, once, so the rest has a baseline ----------------------


def test_registration_credits_once_and_starts_clock_today(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    result = _register(db, staff, serial)

    assert result.points_awarded == 50
    assert result.warranty.status == "active"
    assert result.warranty.warranty_start_date == business_today()
    # 60 months from today, stored explicitly rather than derived at read time.
    assert result.warranty.warranty_end_date.year == business_today().year + 5
    assert result.warranty.warranty_months == 60
    assert ledger.balance(db, dealer.id) == 50


# --- Duplicate serial ------------------------------------------------------


def test_same_dealer_rescanning_replays_instead_of_paying_twice(db):
    """A dealer who loses signal and taps again must not be paid twice."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    first = _register(db, staff, serial)
    second = _register(db, staff, serial)

    assert second.idempotent is True
    assert second.warranty.id == first.warranty.id
    assert ledger.balance(db, dealer.id) == 50, "second scan must not credit again"


def test_second_dealer_cannot_register_an_already_registered_unit(db):
    dealer_a = make_dealer(db, code="D001")
    dealer_b = make_dealer(db, code="D002", name="Shop Two")
    staff_a = make_staff(db, dealer_a, phone="+919000000001")
    staff_b = make_staff(db, dealer_b, phone="+919000000002")
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer_a)

    _register(db, staff_a, serial)

    with pytest.raises(AppError) as exc:
        _register(db, staff_b, serial)
    assert exc.value.code in ("already_registered", "not_your_unit")
    assert ledger.balance(db, dealer_b.id) == 0


def test_database_rejects_a_second_live_warranty_even_if_service_logic_is_bypassed(db):
    """The guarantee must not depend on the service layer being correct."""
    from app.dealer.models.customer import Customer
    from app.dealer.models.warranty import Warranty

    dealer = make_dealer(db)
    make_staff(db, dealer)
    serial = new_serial()
    customer = Customer(phone="+919812345678", name="Asha")
    db.add(customer)
    db.flush()

    common = dict(
        serial=serial,
        warranty_months=60,
        dealer_id=dealer.id,
        customer_id=customer.id,
        warranty_start_date=business_today(),
        warranty_end_date=business_today() + timedelta(days=1800),
        status="active",
    )
    db.add(Warranty(**common))
    db.flush()
    db.add(Warranty(**common))

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --- Cross-dealer registration --------------------------------------------


def test_dealer_cannot_register_a_serial_allocated_to_someone_else(db):
    dealer_a = make_dealer(db, code="D001")
    dealer_b = make_dealer(db, code="D002", name="Shop Two")
    staff_b = make_staff(db, dealer_b, phone="+919000000002")
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer_a)  # allocated to A, B tries to register

    with pytest.raises(AppError) as exc:
        _register(db, staff_b, serial)
    assert exc.value.code == "not_your_unit"
    assert exc.value.status_code == 403
    assert ledger.balance(db, dealer_b.id) == 0


def test_dealer_cannot_register_an_unallocated_serial(db):
    """A serial photographed off someone else's stock is worth nothing."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)  # exists upstream, but allocated to nobody

    with pytest.raises(AppError) as exc:
        _register(db, staff, serial)
    assert exc.value.code == "not_allocated"
    assert ledger.balance(db, dealer.id) == 0


# --- Backdating ------------------------------------------------------------


def test_invoice_date_inside_grace_window_is_honoured(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    three_days_ago = business_today() - timedelta(days=3)
    result = _register(db, staff, serial, invoice_date=three_days_ago)

    assert result.warranty.status == "active"
    assert result.warranty.warranty_start_date == three_days_ago
    assert result.warranty.backdate_days == 3


def test_backdate_beyond_window_parks_for_approval_and_pays_nothing_yet(db):
    """A year-late registration is the exact failure this product exists to stop."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    long_ago = business_today() - timedelta(days=400)
    result = _register(db, staff, serial, invoice_date=long_ago)

    assert result.warranty.status == "pending_backdate"
    assert result.warranty.backdate_days == 400
    assert result.points_awarded == 0
    assert ledger.balance(db, dealer.id) == 0, "must not pay before a human approves"


def test_future_invoice_date_cannot_start_the_clock_late(db):
    """The clock is server-authoritative: a dealer cannot push the start forward."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    next_year = business_today() + timedelta(days=365)
    result = _register(db, staff, serial, invoice_date=next_year)

    assert result.warranty.warranty_start_date == business_today()
    assert result.warranty.backdate_days == 0


def test_approving_a_backdate_activates_and_pays_and_is_audited(db):
    from app.models.audit_log import AuditLog
    from tests.dealer.factories import make_admin

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    result = _register(db, staff, serial, invoice_date=business_today() - timedelta(days=400))
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
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    result = _register(db, staff, serial)
    clawed = warranty_svc.void(
        db, warranty=result.warranty, reason="Customer returned the mattress",
        actor_type="admin", actor_id=admin.id,
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
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)
    result = _register(db, staff, serial)

    # Dealer spends the points before the return comes back.
    ledger.add_entry(
        db, dealer_id=dealer.id, amount=-50, type=ledger.ADMIN_DEBIT,
        admin_id=admin.id, reason="redeemed",
    )
    db.commit()

    warranty_svc.void(
        db, warranty=result.warranty, reason="Returned", actor_type="admin", actor_id=admin.id
    )
    db.commit()
    assert ledger.balance(db, dealer.id) == -50


def test_voided_serial_can_be_registered_again(db):
    """A returned mattress genuinely gets resold; the serial must free up."""
    from tests.dealer.factories import make_admin

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)

    first = _register(db, staff, serial)
    warranty_svc.void(
        db, warranty=first.warranty, reason="Returned", actor_type="admin", actor_id=admin.id
    )
    db.commit()

    second = _register(db, staff, serial, customer_phone="+919888888888", customer_name="Ravi")
    assert second.warranty.id != first.warranty.id
    assert second.warranty.status == "active"
    assert ledger.balance(db, dealer.id) == 50  # 50 - 50 + 50


def test_void_requires_a_reason(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)
    result = _register(db, staff, serial)

    with pytest.raises(AppError) as exc:
        warranty_svc.void(db, warranty=result.warranty, reason="  ")
    assert exc.value.code == "reason_required"


# --- Unit source unreachable ----------------------------------------------


# --- Unknown serials ------------------------------------------------------
#
# These replace the old "unit source unreachable" tests. On a shared database
# there is no third party to be unreachable: if `product_units` has no row, the
# code was never manufactured, and registering anyway would be inventing stock.


def test_a_serial_that_was_never_manufactured_is_refused(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    allocate(db, serial, dealer)  # allocated by mistake; no unit exists

    with pytest.raises(AppError) as exc:
        _register(db, staff, serial)
    assert exc.value.code == "invalid_serial"
    assert exc.value.status_code == 404
    assert ledger.balance(db, dealer.id) == 0


def test_a_product_with_no_rate_registers_but_pays_nothing(db):
    """Recording the sale is the product; the points are the incentive. An
    unpriced product must never block a registration — it just earns zero until
    someone sets a rate, which the admin compliance screen surfaces."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_unit(db, serial)          # real unit, real product, no rate configured
    allocate(db, serial, dealer)

    result = _register(db, staff, serial)
    assert result.warranty.status == "active"
    assert result.points_awarded == 0
    assert ledger.balance(db, dealer.id) == 0


# --- Concurrency -----------------------------------------------------------


def test_parallel_registrations_of_one_serial_create_exactly_one_warranty(session_maker):
    """Real threads, real connections, real Postgres — not a simulated race."""
    from app.dealer.models.ledger_entry import LedgerEntry
    from app.dealer.models.warranty import Warranty

    setup = session_maker()
    dealer = make_dealer(setup)
    staff = make_staff(setup, dealer)
    serial = new_serial()
    make_priced_unit(setup, serial, 50)
    allocate(setup, serial, dealer)
    setup.commit()
    staff_id = staff.id
    setup.close()

    n = 12
    barrier = threading.Barrier(n)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        session = session_maker()
        try:
            from app.dealer.models.dealer import DealerStaff

            local_staff = session.get(DealerStaff, staff_id)
            barrier.wait()
            res = registration.register(
                session,
                staff=local_staff,
                raw_serial=serial,
                customer_phone=f"+91981234{i:04d}",
                customer_name=f"Cust {i}",
                invoice_ref=f"INV-{i}",
            )
            session.commit()
            with lock:
                outcomes.append("replay" if res.idempotent else "created")
        except AppError as exc:
            session.rollback()
            with lock:
                outcomes.append(exc.code)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            with lock:
                outcomes.append(type(exc).__name__)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    verify = session_maker()
    warranties = verify.query(Warranty).filter_by(serial=serial).all()
    credits = (
        verify.query(LedgerEntry).filter_by(type="registration_credit").all()
    )
    assert len(warranties) == 1, f"expected exactly one warranty, got {len(warranties)}"
    assert len(credits) == 1, f"expected exactly one credit, got {len(credits)}"
    assert outcomes.count("created") == 1, f"outcomes={outcomes}"
    verify.close()
