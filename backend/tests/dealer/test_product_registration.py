"""Registration without a scanner, and the one rule that keeps it honest.

Picking a product from a dropdown is easy to do five hundred times. The serial
used to make that pointless — a warranty needed a physical label and each label
paid once — so deleting the serial deletes the cap. At the client's 120 points a
registration, an afternoon of typing would otherwise be worth 60,000 points of
real rewards.

The replacement cap is the dealer's own invoice number: one live warranty per
(dealer, invoice). Every test below is a way that cap could leak — a second
submission of the same bill, a shift key, a trailing space, a race between two
devices — plus the two tests that prove the cap lives in Postgres rather than in
this codebase's good intentions.
"""

import threading
import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import DealerStaff
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.warranty import Warranty
from app.dealer.services import ledger, registration
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.warranty_dates import business_today
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_product,
    make_rate,
    make_staff,
)


def _register(db, staff, product, invoice="INV-1001", **kw):
    defaults = dict(
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
    )
    defaults.update(kw)
    result = registration.register(
        db, staff=staff, product_id=product.id, invoice_ref=invoice, **defaults
    )
    db.commit()
    return result


def _priced_product(db, points=120, months=60):
    product = make_product(db, name=f"Model {uuid.uuid4().hex[:6]}", months=months)
    make_rate(db, points, product=product)
    return product


# --- The happy path --------------------------------------------------------


def test_registering_a_product_pays_its_rate_and_stores_no_serial(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = _priced_product(db, points=120, months=84)

    result = _register(db, staff, product)
    warranty = result.warranty

    assert result.points_awarded == 120
    assert ledger.balance(db, dealer.id) == 120
    assert warranty.status == "active"
    # The product is now the only source of what was sold and how long it lasts.
    assert warranty.product_id == product.id
    assert warranty.model_name == product.name
    assert warranty.warranty_months == 84
    assert warranty.warranty_start_date == business_today()
    # Nothing was scanned, so nothing is claimed about a physical label.
    assert warranty.serial is None
    assert warranty.unit_id is None
    assert warranty.unit_unverified is False
    assert warranty.invoice_ref == "INV-1001"


# --- The product must be real, and still on sale ---------------------------


def test_an_unknown_product_is_refused(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)

    with pytest.raises(AppError) as exc:
        registration.register(
            db,
            staff=staff,
            product_id=uuid.uuid4(),
            customer_phone="+919812345678",
            customer_name="Asha Kumar",
            invoice_ref="INV-1001",
        )
    assert exc.value.code == "invalid_product"
    assert exc.value.status_code == 404
    assert ledger.balance(db, dealer.id) == 0


def test_a_deactivated_product_cannot_still_be_registered(db):
    """Deactivating is how the client stops a discontinued model being sold. An
    app holding a stale dropdown must not keep registering — and keep being paid
    for — a mattress nobody is selling any more."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = _priced_product(db)
    product.is_active = False
    db.commit()

    with pytest.raises(AppError) as exc:
        _register(db, staff, product)
    assert exc.value.code == "invalid_product"
    assert exc.value.status_code == 404
    assert ledger.balance(db, dealer.id) == 0


# --- One live warranty per invoice number ----------------------------------


def test_the_same_invoice_twice_is_refused_and_pays_once(db):
    """The whole cap, in one test: a second submission of one bill earns nothing."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = _priced_product(db, points=120)

    _register(db, staff, product, invoice="INV-1001")

    with pytest.raises(AppError) as exc:
        _register(db, staff, product, invoice="INV-1001", customer_phone="+919888888888")
    assert exc.value.code == "duplicate_invoice"
    assert exc.value.status_code == 409
    db.rollback()

    assert db.query(Warranty).count() == 1
    assert ledger.balance(db, dealer.id) == 120, "the second attempt must not be paid"


@pytest.mark.parametrize("second", ["inv-1001", "InV-1001", "  INV-1001  "])
def test_a_shift_key_or_a_stray_space_does_not_buy_a_second_registration(db, second):
    """Without lower() in the index, "INV-1" and "inv-1" are two rows and the cap
    is one keystroke away. Trailing spaces are the same hole by another route,
    which is why the invoice is trimmed before it is stored."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = _priced_product(db, points=120)

    _register(db, staff, product, invoice="INV-1001")

    with pytest.raises(AppError) as exc:
        _register(db, staff, product, invoice=second, customer_phone="+919888888888")
    assert exc.value.code == "duplicate_invoice"
    db.rollback()
    assert ledger.balance(db, dealer.id) == 120


def test_two_dealers_may_use_the_same_invoice_number(db):
    """Invoice numbers are each shop's own counter. Nearly every shop's first
    sale is "INV-1"; scoping the rule per dealer is what keeps the cap from
    turning into "only one shop in India may use this number"."""
    shop_a = make_dealer(db, code="D001")
    shop_b = make_dealer(db, code="D002", name="Shop Two")
    staff_a = make_staff(db, shop_a, phone="+919000000001")
    staff_b = make_staff(db, shop_b, phone="+919000000002")
    product = _priced_product(db, points=120)

    first = _register(db, staff_a, product, invoice="INV-1")
    second = _register(db, staff_b, product, invoice="INV-1", customer_phone="+919888888888")

    assert first.warranty.id != second.warranty.id
    assert ledger.balance(db, shop_a.id) == 120
    assert ledger.balance(db, shop_b.id) == 120


def test_voiding_a_warranty_frees_its_invoice_number(db):
    """A returned sale is re-entered under the same bill. The index only counts
    live warranties, so voiding gives the number back rather than burning it."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    product = _priced_product(db, points=120)

    first = _register(db, staff, product, invoice="INV-1001")
    warranty_svc.void(
        db,
        warranty=first.warranty,
        reason="Customer returned the mattress",
        actor_type="admin",
        actor_id=admin.id,
    )
    db.commit()

    second = _register(db, staff, product, invoice="INV-1001", customer_name="Ravi")

    assert second.warranty.id != first.warranty.id
    assert second.warranty.status == "active"
    assert ledger.balance(db, dealer.id) == 120, "120 earned, 120 clawed back, 120 earned"


# --- Where the guarantee actually lives ------------------------------------


def test_the_index_rejects_a_case_only_duplicate_written_behind_the_service(db):
    """The cap must not depend on registration.py being correct. Two rows, one
    invoice, different case, inserted straight into the table."""
    dealer = make_dealer(db)
    customer = Customer(phone="+919812345678", name="Asha")
    db.add(customer)
    db.flush()

    common = dict(
        serial=None,
        warranty_months=60,
        dealer_id=dealer.id,
        customer_id=customer.id,
        warranty_start_date=business_today(),
        warranty_end_date=business_today() + timedelta(days=1800),
        status="active",
    )
    db.add(Warranty(invoice_ref="INV-1001", **common))
    db.flush()
    db.add(Warranty(invoice_ref="inv-1001", **common))

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_parallel_submissions_of_one_invoice_create_exactly_one_warranty(
    session_maker, monkeypatch
):
    """Real threads, real connections, real Postgres — with the service's own
    duplicate check removed.

    That removal is the point. Two devices submitting the same bill at the same
    instant both run their SELECT before either commits, so both see nothing and
    both proceed; a check in Python cannot lose that race safely. Patching the
    check out is the only way to prove the survivor is the DATABASE. Drop
    uq_warranties_live_dealer_invoice and this test pays twelve times for one
    sale.
    """
    monkeypatch.setattr(registration, "_reject_duplicate_invoice", lambda *a, **kw: None)

    setup = session_maker()
    dealer = make_dealer(setup)
    staff = make_staff(setup, dealer)
    product = _priced_product(setup, points=120)
    setup.commit()
    staff_id, dealer_id, product_id = staff.id, dealer.id, product.id
    setup.close()

    n = 12
    barrier = threading.Barrier(n)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        session = session_maker()
        try:
            local_staff = session.get(DealerStaff, staff_id)
            barrier.wait()
            registration.register(
                session,
                staff=local_staff,
                product_id=product_id,
                customer_phone=f"+91981234{i:04d}",
                customer_name=f"Cust {i}",
                invoice_ref="INV-1001",
            )
            session.commit()
            with lock:
                outcomes.append("created")
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
    warranties = verify.query(Warranty).all()
    credits = verify.query(LedgerEntry).filter_by(type="registration_credit").all()
    assert len(warranties) == 1, f"expected one warranty, got {len(warranties)}: {outcomes}"
    assert len(credits) == 1, f"expected one credit, got {len(credits)}: {outcomes}"
    assert outcomes.count("created") == 1, f"outcomes={outcomes}"
    # Everything else must be the clean 409, not a raw IntegrityError leaking to
    # the dealer as a 500.
    assert set(outcomes) - {"created"} == {"duplicate_invoice"}, f"outcomes={outcomes}"
    assert ledger.balance(verify, dealer_id) == 120
    verify.close()
