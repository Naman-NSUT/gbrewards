"""Two ways a real registration silently stopped telling the truth about itself.

FIRST: the dealer correction route took the warranty id as a plain string and
handed it straight to the database. A junk path segment therefore died inside
psycopg instead of at the edge, which cost a 500 and — worse — gave anyone
poking at the route a distinguishable answer that the deliberate "same 404 for
does-not-exist and belongs-to-another-dealer" defence exists to deny.

SECOND: the public confirm endpoint's guard for the customer_verified event was
written against a flag the service call immediately above it had already set, so
the branch could never be taken. The customer's tap — the one piece of evidence
that turns a dealer's CLAIM of a sale into proof of one, and the thing a
disputed claim turns on years later — was never written to the timeline on the
default configuration, which is every warranty in production.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from app.dealer.models.warranty import WarrantyEvent
from app.dealer.services import registration
from app.main import create_app
from tests.dealer.factories import (
    make_dealer,
    make_priced_unit,
    make_staff,
    new_serial,
)

DEALER = "/api/v1/dealer"
PUB = "/api/v1/public"

CUSTOMER_PHONE = "+919812345678"
LAST4 = "5678"


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    def _get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    # raise_server_exceptions=False so an unhandled exception inside a route
    # reaches this test as the 500 a real customer would see, instead of being
    # re-raised into the test and masquerading as a test error. Without it the
    # pre-fix behaviour of the correction route is invisible.
    import fakeredis

    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fake
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _register(db, *, dealer_code="D001", staff_phone="+919000000001", phone=CUSTOMER_PHONE):
    """A real dealer registration, committed so the client's session sees it."""
    dealer = make_dealer(db, code=dealer_code)
    staff = make_staff(db, dealer, phone=staff_phone)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    result = registration.register(
        db,
        staff=staff,
        raw_serial=serial,
        customer_phone=phone,
        customer_name="Asha Kumar",
        invoice_ref="INV-1",
    )
    db.commit()
    return dealer, staff, result.warranty


def _auth(staff):  # type: ignore[no-untyped-def]
    return {"Authorization": f"Bearer {create_access_token(str(staff.id), 'dealer')}"}


def _verified_events(db, warranty_id):  # type: ignore[no-untyped-def]
    return (
        db.query(WarrantyEvent).filter_by(warranty_id=warranty_id, event="customer_verified").all()
    )


# --------------------------------------------------------------------------
# Fix 1 — a malformed id must be refused at the edge, not in psycopg
# --------------------------------------------------------------------------


@pytest.mark.parametrize("junk", ["abc", "12345", "not-a-uuid", "0000"])
def test_a_malformed_registration_id_is_a_422_not_a_500(client, db, junk):
    """Anything a fat finger or a fuzzer can put in the path must be rejected by
    validation. Typed as a bare string it instead reached the database, where
    'invalid input syntax for type uuid' aborted the request transaction."""
    _, staff, _ = _register(db)

    resp = client.patch(
        f"{DEALER}/registrations/{junk}/customer",
        json={"customer_name": "Asha Kumari"},
        headers=_auth(staff),
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "validation_error"


def test_a_prober_gets_only_two_answers_for_an_id_that_is_not_theirs(client, db):
    """The 404 below deliberately conflates "no such registration" with "someone
    else's registration". A crash on a malformed id undoes that: it is a third,
    handler-level answer, and a 500 is exactly what someone fuzzing an endpoint
    is looking for. After the fix a malformed id never reaches the handler at
    all — 422 is the framework saying "that is not a UUID", decided before any
    lookup, so it reveals nothing about what is in the database."""
    _, staff, _ = _register(db)
    _, _, other = _register(db, dealer_code="D002", staff_phone="+919000000002")
    headers = _auth(staff)

    unknown = client.patch(
        f"{DEALER}/registrations/{uuid.uuid4()}/customer",
        json={"customer_name": "X"},
        headers=headers,
    )
    someone_elses = client.patch(
        f"{DEALER}/registrations/{other.id}/customer",
        json={"customer_name": "X"},
        headers=headers,
    )
    malformed = client.patch(
        f"{DEALER}/registrations/nonsense/customer",
        json={"customer_name": "X"},
        headers=headers,
    )

    assert unknown.status_code == 404
    assert someone_elses.status_code == 404
    assert someone_elses.json() == unknown.json(), (
        "a dealer must not be able to tell 'does not exist' from 'not yours'"
    )
    assert malformed.status_code == 422
    assert 500 not in (unknown.status_code, someone_elses.status_code, malformed.status_code)


# --------------------------------------------------------------------------
# Fix 2 — the customer's tap must actually be recorded
# --------------------------------------------------------------------------


def test_the_customer_tap_is_recorded_once_with_its_source_ip(client, db):
    """The default path: REQUIRE_CUSTOMER_CONFIRMATION is off, so the warranty is
    already active and the service call changes no status. The acknowledgement is
    still the most valuable signal this system collects and must be written."""
    _, _, warranty = _register(db)

    resp = client.post(
        f"{PUB}/w/{warranty.id}/confirm",
        json={"last4": LAST4},
        headers={"x-forwarded-for": "203.0.113.7"},
    )
    assert resp.status_code == 200, resp.text

    events = _verified_events(db, warranty.id)
    assert len(events) == 1, "the tap on the SMS link was never recorded"
    assert events[0].actor_type == "customer"
    assert events[0].actor_id == warranty.customer_id
    assert events[0].event_metadata["ip"] == "203.0.113.7", (
        "the source IP is half the evidence — it is what makes the tap checkable later"
    )


def test_refreshing_the_confirmation_page_does_not_record_the_tap_twice(client, db):
    """A customer who taps, loses signal and taps again has acknowledged once.
    Two events would read on the timeline as two separate acts."""
    _, _, warranty = _register(db)
    body = {"last4": LAST4}

    assert client.post(f"{PUB}/w/{warranty.id}/confirm", json=body).status_code == 200
    assert client.post(f"{PUB}/w/{warranty.id}/confirm", json=body).status_code == 200

    assert len(_verified_events(db, warranty.id)) == 1


def test_a_second_mattress_for_the_same_customer_gets_its_own_acknowledgement(client, db):
    """The reason the guard keys on confirmed_at and not on is_phone_verified.

    is_phone_verified lives on the CUSTOMER and is set for life by the first
    confirmation. Keying the evidence on it would mean a repeat buyer — exactly
    the customer worth keeping — silently acknowledges nothing from their second
    mattress onward, and the warranty that most needs the evidence is the one
    that has none."""
    dealer = make_dealer(db, code="D001")
    staff = make_staff(db, dealer)
    warranties = []
    for ref in ("INV-1", "INV-2"):
        serial = new_serial()
        make_priced_unit(db, serial, 50)
        result = registration.register(
            db,
            staff=staff,
            raw_serial=serial,
            customer_phone=CUSTOMER_PHONE,
            customer_name="Asha Kumar",
            invoice_ref=ref,
        )
        warranties.append(result.warranty)
    db.commit()

    first, second = warranties
    assert first.customer_id == second.customer_id, "same buyer, two mattresses"

    for warranty in warranties:
        resp = client.post(f"{PUB}/w/{warranty.id}/confirm", json={"last4": LAST4})
        assert resp.status_code == 200, resp.text

    assert len(_verified_events(db, first.id)) == 1
    assert len(_verified_events(db, second.id)) == 1, (
        "the second mattress needs its own evidence; the customer's phone being "
        "verified already says nothing about THIS sale"
    )


def test_the_tap_is_recorded_once_when_it_also_activates_the_warranty(client, db, monkeypatch):
    """The opt-in path: the warranty is waiting on this tap, so the same request
    both activates it and is the acknowledgement. One event, not zero and not
    two — the service writes the 'confirmed' transition, this writes the
    customer's act and its IP."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "require_customer_confirmation", True)
    _, _, warranty = _register(db)
    assert warranty.status == "pending_confirmation"

    resp = client.post(
        f"{PUB}/w/{warranty.id}/confirm",
        json={"last4": LAST4},
        headers={"x-forwarded-for": "198.51.100.4"},
    )
    assert resp.status_code == 200, resp.text

    db.expire_all()
    assert warranty.status == "active"
    events = _verified_events(db, warranty.id)
    assert len(events) == 1
    assert events[0].event_metadata["ip"] == "198.51.100.4"
    transitions = db.query(WarrantyEvent).filter_by(warranty_id=warranty.id, event="confirmed")
    assert transitions.count() == 1


def test_a_claimed_warranty_records_no_acknowledgement(client, db):
    """confirm() refuses any status outside pending_confirmation/active, leaving
    confirmed_at unset. The guard keys on confirmed_at precisely so that a tap
    the service declined does not leave evidence claiming it was accepted."""
    _, _, warranty = _register(db)
    warranty.status = "claimed"
    db.commit()

    resp = client.post(f"{PUB}/w/{warranty.id}/confirm", json={"last4": LAST4})
    assert resp.status_code == 200, resp.text

    db.expire_all()
    assert warranty.confirmed_at is None
    assert _verified_events(db, warranty.id) == []


def test_the_acknowledgement_reaches_the_admin_timeline(client, db):
    """The event is not an internal detail: build_warranty_detail is what the
    admin warranty screen renders, and it shows WarrantyEvents. An unreachable
    branch meant the timeline silently never showed the customer's reply."""
    from app.dealer.api.admin.warranties import build_warranty_detail

    dealer, _, warranty = _register(db)

    resp = client.post(
        f"{PUB}/w/{warranty.id}/confirm",
        json={"last4": LAST4},
        headers={"x-forwarded-for": "203.0.113.9"},
    )
    assert resp.status_code == 200, resp.text

    db.expire_all()
    detail = build_warranty_detail(db, warranty, warranty.customer, dealer)
    timeline = [e.event for e in detail.events]
    assert "customer_verified" in timeline, (
        "an admin looking at a disputed sale must be able to see that the buyer confirmed it"
    )
