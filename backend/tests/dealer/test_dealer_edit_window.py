"""The dealer edit window — a typo is fixable for a day, a reassignment is not."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.core.security import create_access_token
from app.dealer.models.warranty import Warranty
from app.main import create_app
from app.models.audit_log import AuditLog
from tests.dealer.factories import (
    allocate,
    make_dealer,
    make_priced_unit,
    make_staff,
    new_serial,
)


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    def _get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c


def _setup(db, code="D001", phone="+919000000001"):
    dealer = make_dealer(db, code=code)
    staff = make_staff(db, dealer, phone=phone)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)
    db.commit()
    return dealer, staff, serial


def _register(client, staff, serial, phone="9812345678"):
    token = create_access_token(str(staff.id), "dealer")
    resp = client.post(
        "/api/v1/dealer/registrations",
        json={
            "serial": serial,
            "customer_phone": phone,
            "customer_name": "Asha Kumar",
            "invoice_ref": "INV-1",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["warranty"]["id"], {"Authorization": f"Bearer {token}"}


def test_dealer_can_fix_a_mistyped_number_inside_the_window(client, db):
    _, staff, serial = _setup(db)
    warranty_id, headers = _register(client, staff, serial, phone="9812345678")

    resp = client.patch(
        f"/api/v1/dealer/registrations/{warranty_id}/customer",
        json={"customer_phone": "9812345679"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["customer_phone"] == "+919812345679"
    assert resp.json()["resent_sms"] is True, "fixing the number must resend the SMS"


def test_correction_is_audited_with_before_and_after(client, db):
    _, staff, serial = _setup(db)
    warranty_id, headers = _register(client, staff, serial)

    client.patch(
        f"/api/v1/dealer/registrations/{warranty_id}/customer",
        json={"customer_name": "Asha Kumari"},
        headers=headers,
    )
    audit = db.query(AuditLog).filter_by(action="edit_customer").one()
    assert audit.actor_type == "dealer_staff"
    assert audit.audit_metadata["before"]["name"] == "Asha Kumar"
    assert audit.audit_metadata["after"]["name"] == "Asha Kumari"


def test_window_closes_after_the_configured_hours(client, db):
    _, staff, serial = _setup(db)
    warranty_id, headers = _register(client, staff, serial)

    # Age the registration past the window.
    warranty = db.get(Warranty, uuid.UUID(warranty_id))
    warranty.registered_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()

    resp = client.patch(
        f"/api/v1/dealer/registrations/{warranty_id}/customer",
        json={"customer_phone": "9812345679"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "edit_window_closed"


def test_a_dealer_cannot_edit_another_dealers_registration(client, db):
    _, staff_a, serial = _setup(db, code="D001", phone="+919000000001")
    dealer_b = make_dealer(db, code="D002", name="Shop Two")
    staff_b = make_staff(db, dealer_b, phone="+919000000002")
    db.commit()

    warranty_id, _ = _register(client, staff_a, serial)
    token_b = create_access_token(str(staff_b.id), "dealer")

    resp = client.patch(
        f"/api/v1/dealer/registrations/{warranty_id}/customer",
        json={"customer_phone": "9812345679"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    # 404, not 403: this endpoint must not confirm that another dealer's
    # registration exists.
    assert resp.status_code == 404


def test_moving_to_a_new_number_does_not_corrupt_the_original_customer(client, db):
    """The mistyped number may belong to a real customer with other mattresses."""
    from app.dealer.models.customer import Customer

    _, staff, serial = _setup(db)
    warranty_id, headers = _register(client, staff, serial, phone="9812345678")

    client.patch(
        f"/api/v1/dealer/registrations/{warranty_id}/customer",
        json={"customer_phone": "9812345679"},
        headers=headers,
    )

    # The original customer row still exists, unchanged.
    original = db.query(Customer).filter_by(phone="+919812345678").one_or_none()
    assert original is not None
    assert original.name == "Asha Kumar"
    # And the warranty now points at a different customer.
    warranty = db.get(Warranty, uuid.UUID(warranty_id))
    db.refresh(warranty)
    assert warranty.customer.phone == "+919812345679"
