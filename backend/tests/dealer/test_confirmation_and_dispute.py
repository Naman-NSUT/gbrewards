"""Customer acknowledgment and dispute.

The confirmation reply is the only thing that turns a dealer's CLAIM of a sale
into EVIDENCE of one, so it must be recorded on the default path too — where the
warranty is already active and there is no status change to make.
"""

import pytest

from app.dealer.models.audit_log import DealerAuditLog as AuditLog
from app.dealer.models.warranty import WarrantyEvent
from app.dealer.services import ledger, registration
from app.dealer.services import warranty as warranty_svc
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_priced_unit,
    make_rate,
    make_staff,
    new_serial,
)


def _register(db, *, dealer=None, staff=None):
    dealer = dealer or make_dealer(db)
    staff = staff or make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    result = registration.register(
        db,
        staff=staff,
        raw_serial=serial,
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
        invoice_ref="INV-1",
    )
    db.commit()
    return result


def test_confirming_an_already_active_warranty_records_the_acknowledgment(db):
    """The default config path. This must NOT be a silent no-op — it is the
    majority case and the most valuable signal the system collects."""
    result = _register(db)
    warranty = result.warranty
    assert warranty.status == "active"
    assert warranty.confirmed_at is None
    assert warranty.customer.is_phone_verified is False

    points = warranty_svc.confirm(db, warranty=warranty)
    db.commit()

    assert points == 0, "no points move; the warranty was already active and paid"
    assert warranty.confirmed_at is not None, "the acknowledgment must be recorded"
    assert warranty.customer.is_phone_verified is True, (
        "this is what distinguishes a dealer-typed number from a proven one"
    )
    event = db.query(WarrantyEvent).filter_by(warranty_id=warranty.id, event="confirmed").one()
    assert event.event_metadata["activated"] is False


def test_confirming_twice_does_not_duplicate_the_event(db):
    result = _register(db)
    warranty_svc.confirm(db, warranty=result.warranty)
    db.commit()
    first_at = result.warranty.confirmed_at

    warranty_svc.confirm(db, warranty=result.warranty)
    db.commit()

    assert result.warranty.confirmed_at == first_at
    events = (
        db.query(WarrantyEvent).filter_by(warranty_id=result.warranty.id, event="confirmed").all()
    )
    assert len(events) == 1


def test_confirmation_activates_and_pays_when_the_warranty_was_waiting(db, monkeypatch):
    """The opt-in path: REQUIRE_CUSTOMER_CONFIRMATION on."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "require_customer_confirmation", True)
    result = _register(db)
    warranty = result.warranty

    assert warranty.status == "pending_confirmation"
    assert result.points_awarded == 0, "must not pay before the customer confirms"
    assert ledger.balance(db, warranty.dealer_id) == 0

    points = warranty_svc.confirm(db, warranty=warranty)
    db.commit()

    assert points == 50
    assert warranty.status == "active"
    assert ledger.balance(db, warranty.dealer_id) == 50


def test_confirming_a_voided_warranty_does_nothing(db):
    result = _register(db)
    admin = make_admin(db)
    warranty_svc.void(
        db, warranty=result.warranty, reason="Returned", actor_type="admin", actor_id=admin.id
    )
    db.commit()

    assert warranty_svc.confirm(db, warranty=result.warranty) == 0
    assert result.warranty.status == "voided"


def test_dispute_does_not_void_and_leaves_the_points_alone(db):
    """Anyone holding the SMS link could otherwise destroy a genuine sale."""
    result = _register(db)
    warranty = result.warranty
    dealer_id = warranty.dealer_id

    warranty_svc.dispute(db, warranty=warranty, reason="I never bought this")
    db.commit()

    assert warranty.status == "active", "a dispute must not void — it flags for a human"
    assert ledger.balance(db, dealer_id) == 50, "points survive until a human decides"

    event = db.query(WarrantyEvent).filter_by(warranty_id=warranty.id, event="disputed").one()
    assert event.reason == "I never bought this"

    audit = db.query(AuditLog).filter_by(action="dispute_warranty").one()
    assert audit.actor_type == "customer"
    assert audit.reason == "I never bought this"


def test_approving_a_self_registration_can_reject_the_claimed_date(db):
    """An approver accepting the sale but not the customer's stated purchase date
    must be able to reset the clock — previously only possible for backdates."""
    from datetime import timedelta

    from app.dealer.models.customer import Customer
    from app.dealer.models.warranty import Warranty
    from app.dealer.services.warranty_dates import business_today

    dealer = make_dealer(db)
    admin = make_admin(db)
    make_rate(db, 50)
    serial = new_serial()
    customer = Customer(phone="+919812345678", name="Asha")
    db.add(customer)
    db.flush()

    claimed_start = business_today() - timedelta(days=420)
    warranty = Warranty(
        serial=serial,
        warranty_months=60,
        dealer_id=dealer.id,
        customer_id=customer.id,
        warranty_start_date=claimed_start,
        warranty_end_date=claimed_start + timedelta(days=1800),
        status="pending_review",
        source="customer_self",
    )
    db.add(warranty)
    db.flush()

    warranty_svc.approve(
        db,
        warranty=warranty,
        admin_id=admin.id,
        reason="Invoice illegible; accepting the sale on today's clock",
        honour_requested_date=False,
    )
    db.commit()

    assert warranty.status == "active"
    assert warranty.warranty_start_date == business_today()
    assert warranty.backdate_days == 0
    # A self-registration pays nobody: the dealer did not do the work.
    assert ledger.balance(db, dealer.id) == 0


@pytest.mark.parametrize("status", ["pending_review", "pending_backdate"])
def test_confirmation_is_meaningless_while_a_warranty_awaits_review(db, status):
    result = _register(db)
    result.warranty.status = status
    db.commit()
    assert warranty_svc.confirm(db, warranty=result.warranty) == 0
    assert result.warranty.confirmed_at is None
