"""End-to-end idempotency, through the real HTTP layer.

The dealer app queues submissions on a bad connection and replays them. These
tests are the contract that queue depends on.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from app.main import create_app
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

    # Rate limiters are per IP and every test calls from the same one, so a
    # shared real Redis would make later tests fail on counters earlier tests
    # ran up. A fresh fake per test keeps them independent.
    import fakeredis

    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fake
    with TestClient(app) as c:
        yield c


@pytest.fixture
def scenario(db):  # type: ignore[no-untyped-def]
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)
    db.commit()
    token = create_access_token(str(staff.id), "dealer")
    return {
        "dealer": dealer,
        "staff": staff,
        "serial": serial,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def _body(serial: str, **kw):
    payload = {
        "serial": serial,
        "customer_phone": "9812345678",
        "customer_name": "Asha Kumar",
        "invoice_ref": "INV-1001",
    }
    payload.update(kw)
    return payload


def test_retry_with_same_key_replays_the_original_response(client, scenario, db):
    key = str(uuid.uuid4())
    headers = {**scenario["headers"], "Idempotency-Key": key}
    body = _body(scenario["serial"])

    first = client.post("/api/v1/dealer/registrations", json=body, headers=headers)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/dealer/registrations", json=body, headers=headers)

    assert second.status_code == 201
    assert second.json()["warranty"]["id"] == first.json()["warranty"]["id"]
    assert second.json()["points_awarded"] == first.json()["points_awarded"]

    from app.dealer.models.ledger_entry import LedgerEntry
    from app.dealer.models.warranty import Warranty

    fresh = db.query(Warranty).filter_by(serial=scenario["serial"]).all()
    credits = db.query(LedgerEntry).filter_by(type="registration_credit").all()
    assert len(fresh) == 1, "a retry must not create a second warranty"
    assert len(credits) == 1, "a retry must not credit twice"


def test_missing_idempotency_key_is_rejected(client, scenario):
    resp = client.post(
        "/api/v1/dealer/registrations",
        json=_body(scenario["serial"]),
        headers=scenario["headers"],
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "idempotency_key_required"


def test_same_key_with_a_different_body_is_rejected_loudly(client, scenario):
    """Not a retry — a client bug or an attack. Replaying the first result here
    would attach one customer's details to another's warranty."""
    key = str(uuid.uuid4())
    headers = {**scenario["headers"], "Idempotency-Key": key}

    first = client.post(
        "/api/v1/dealer/registrations", json=_body(scenario["serial"]), headers=headers
    )
    assert first.status_code == 201

    resp = client.post(
        "/api/v1/dealer/registrations",
        json=_body(scenario["serial"], customer_phone="9999999999", customer_name="Someone Else"),
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "idempotency_key_reused"


def test_failed_registration_frees_the_key_so_a_real_retry_works(client, scenario, db):
    """A transient failure must not wedge the key at 'in progress' forever."""
    key = str(uuid.uuid4())
    headers = {**scenario["headers"], "Idempotency-Key": key}

    # Unallocated serial → the registration fails.
    bad = client.post("/api/v1/dealer/registrations", json=_body(new_serial()), headers=headers)
    assert bad.status_code == 403
    assert bad.json()["error"]["code"] == "not_allocated"

    from app.dealer.models.idempotency import IdempotencyKey

    assert db.query(IdempotencyKey).filter_by(key=key).one_or_none() is None

    # The dealer scans the right unit and reuses the same queued key.
    good = client.post(
        "/api/v1/dealer/registrations", json=_body(scenario["serial"]), headers=headers
    )
    assert good.status_code == 201, good.text


def test_phone_is_normalised_so_the_customer_can_be_found_later(client, scenario, db):
    key = str(uuid.uuid4())
    headers = {**scenario["headers"], "Idempotency-Key": key}
    resp = client.post(
        "/api/v1/dealer/registrations",
        json=_body(scenario["serial"], customer_phone="0 98123 45678"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["customer"]["phone"] == "+919812345678"


def test_a_dealer_token_cannot_reach_admin_scoped_state(client, scenario):
    """Audience separation: a dealer token is not an admin token."""
    from app.core.security import create_access_token as mint

    admin_token = mint(str(uuid.uuid4()), "dealer_admin")
    resp = client.get("/api/v1/dealer/points", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_token"


def test_preview_reports_a_cross_dealer_unit_as_not_registerable(client, db, scenario):
    other = make_dealer(db, code="D999", name="Other Shop")
    other_serial = new_serial()
    make_priced_unit(db, other_serial, 50)
    allocate(db, other_serial, other)
    db.commit()

    resp = client.get(f"/api/v1/dealer/units/{other_serial}/preview", headers=scenario["headers"])
    assert resp.status_code == 200
    assert resp.json()["registerable"] is False
    assert "different dealer" in resp.json()["reason"]
