"""The public customer site's API.

Unauthenticated and reachable by anyone, so these tests care most about what it
REFUSES to say: a serial photographed in a shop must not reveal the buyer, and a
leaked warranty link must not be enough to act on the record.

Two fixtures, because this endpoint now serves two eras. `sale` is a warranty
registered the way every warranty is registered today — a product and an invoice
number, no serial anywhere. `legacy_sale` is one from before the dropdown
replaced the scanner, and it is the only kind the serial-addressed half of this
API (lookup by serial, and claims) can still find at all.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.dealer.services import registration
from app.main import create_app
from tests.dealer.factories import (
    make_dealer,
    make_legacy_warranty,
    make_priced_product,
    make_staff,
    make_unit,
    new_invoice,
    new_serial,
)

PUB = "/api/v1/public"


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    def _get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

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
def sale(db):  # type: ignore[no-untyped-def]
    """A sale registered today: a product from the dropdown, and a bill."""
    dealer = make_dealer(db, code="D001", name="Sunrise Beds")
    dealer.city = "Nagpur"
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)
    result = registration.register(
        db,
        staff=staff,
        product_id=product.id,
        customer_phone="+919812345678",
        customer_name="Meera Iyer",
        invoice_ref=new_invoice(),
    )
    db.commit()
    return {"dealer": dealer, "warranty": result.warranty}


@pytest.fixture
def legacy_sale(db):  # type: ignore[no-untyped-def]
    """A sale from before the scanner was retired, so it still has a serial.

    Nothing writes rows like this any more, but they are what the serial half of
    this API answers about: a five-year warranty sold last year is live for four
    more, and the only reference its owner holds is the code under the QR.
    """
    dealer = make_dealer(db, code="D002", name="Moonlight Mattress")
    dealer.city = "Nagpur"
    serial = new_serial()
    make_unit(db, serial)
    warranty = make_legacy_warranty(
        db,
        dealer=dealer,
        serial=serial,
        customer_phone="+919812345678",
        customer_name="Meera Iyer",
        invoice_ref="INV-OLD-1",
    )
    db.commit()
    return {"dealer": dealer, "serial": serial, "warranty": warranty}


def test_lookup_by_mobile_finds_the_warranty(client, sale):
    """The mobile number is now the ONLY handle a new buyer has on their record.
    Nothing is printed on the mattress for them to type instead."""
    body = client.post(f"{PUB}/lookup", json={"phone": "9812345678"}).json()
    assert len(body["results"]) == 1
    row = body["results"][0]
    assert row["status"] == "active"
    assert row["dealer"]["name"] == "Sunrise Beds"
    assert row["dealer"]["city"] == "Nagpur"


def test_lookup_by_serial_masks_the_buyer(client, legacy_sale):
    """Anyone can photograph a label in a shop. They must not learn who bought it."""
    body = client.post(f"{PUB}/lookup", json={"serial": legacy_sale["serial"]}).json()
    assert len(body["results"]) == 1
    row = body["results"][0]
    assert "Meera Iyer" not in str(row), "the buyer's real name must never appear"
    assert "9812345678" not in str(row).replace("+91", ""), "nor their real number"
    assert "*" in row["customer"]["name"] and "*" in row["customer"]["phone"]


def test_lookup_rejects_both_fields_at_once(client):
    resp = client.post(f"{PUB}/lookup", json={"phone": "9812345678", "serial": "abc"})
    assert resp.status_code == 422


def test_nothing_found_points_at_self_registration_without_a_404(client):
    resp = client.post(f"{PUB}/lookup", json={"phone": "9999999999"})
    assert resp.status_code == 200, "a miss is an answer, not an error"
    body = resp.json()
    assert body["results"] == []
    assert body["can_self_register"] is True
    assert body["message"]


def test_self_registration_queues_for_review_and_pays_nobody(client, db):
    """The flow this product exists to expose: the dealer never registered, so
    the customer does. It must NOT credit the dealer who failed to."""
    from app.dealer.services import ledger

    dealer = make_dealer(db, code="D009", name="Silent Beds")
    serial = new_serial()
    make_unit(db, serial)
    db.commit()

    resp = client.post(
        f"{PUB}/self-registrations",
        data={
            "serial": serial,
            "customer_name": "Ravi Kumar",
            "customer_phone": "9812300099",
            "purchase_date": "2026-01-15",
            # with no allocations, the CUSTOMER naming the shop is the only
            # attribution there is — and it is the stronger evidence anyway
            "dealer_hint": "D009",
        },
        files={"proof": ("bill.jpg", b"\xff\xd8\xff" + b"x" * 200, "image/jpeg")},
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["status"] == "submitted"

    from app.dealer.models.warranty import Warranty

    w = db.query(Warranty).filter_by(serial=serial).one()
    assert w.status == "pending_review"
    assert w.source == "customer_self"
    assert w.dealer_id == dealer.id, "the shop the customer named must be on the record"
    assert ledger.balance(db, dealer.id) == 0, "a self-registration pays nobody"


def test_self_registration_refuses_an_oversized_or_wrong_file(client, db):
    make_dealer(db)
    serial = new_serial()
    make_unit(db, serial)
    db.commit()

    resp = client.post(
        f"{PUB}/self-registrations",
        data={
            "serial": serial,
            "customer_name": "Ravi",
            "customer_phone": "9812300098",
            "purchase_date": "2026-01-15",
        },
        files={"proof": ("bill.exe", b"MZ" + b"x" * 100, "application/x-msdownload")},
    )
    assert resp.status_code in (400, 415, 422)


def test_the_sms_link_needs_the_last_four_digits(client, sale):
    """A leaked warranty id alone must not be enough to see or change anything."""
    wid = sale["warranty"].id

    assert client.get(f"{PUB}/w/{wid}?last4=0000").status_code == 403
    ok = client.get(f"{PUB}/w/{wid}?last4=5678")
    assert ok.status_code == 200, ok.text
    assert ok.json()["warranty"]["status"] == "active"


def test_confirming_records_the_customers_acknowledgment(client, db, sale):
    wid = sale["warranty"].id
    resp = client.post(f"{PUB}/w/{wid}/confirm", json={"last4": "5678"})
    assert resp.status_code == 200, resp.text

    db.refresh(sale["warranty"])
    assert sale["warranty"].confirmed_at is not None
    assert sale["warranty"].customer.is_phone_verified is True


def test_disputing_flags_for_a_human_rather_than_voiding(client, db, sale):
    """Anyone holding the SMS link could otherwise destroy a real sale."""
    from app.dealer.services import ledger

    wid = sale["warranty"].id
    resp = client.post(
        f"{PUB}/w/{wid}/dispute", json={"last4": "5678", "note": "I never bought this"}
    )
    assert resp.status_code == 200, resp.text

    db.refresh(sale["warranty"])
    assert sale["warranty"].status == "active", "a dispute must not void"
    assert ledger.balance(db, sale["dealer"].id) == 50, "points survive until a human decides"


def test_claims_require_the_registered_mobile(client, db, legacy_sale):
    """Otherwise anyone can raise claims on someone else's mattress."""
    wrong = client.post(
        f"{PUB}/claims",
        json={
            "serial": legacy_sale["serial"],
            "phone": "9999999999",
            "description": "Sagging badly after two months",
            "issue_type": "sagging",
        },
    )
    assert wrong.status_code in (403, 404)

    right = client.post(
        f"{PUB}/claims",
        json={
            "serial": legacy_sale["serial"],
            "phone": "9812345678",
            "description": "Sagging badly after two months",
            "issue_type": "sagging",
        },
    )
    assert right.status_code in (200, 201), right.text
    reference = right.json()["reference"]
    assert len(reference) >= 6

    status = client.post(
        f"{PUB}/claims/status", json={"reference": reference, "phone": "9812345678"}
    )
    assert status.status_code == 200
    assert status.json()["reference"] == reference


def test_claim_status_needs_the_matching_mobile(client, db, legacy_sale):
    right = client.post(
        f"{PUB}/claims",
        json={
            "serial": legacy_sale["serial"],
            "phone": "9812345678",
            "description": "Sagging badly after two months",
            "issue_type": "sagging",
        },
    )
    assert right.status_code in (200, 201), right.text
    reference = right.json()["reference"]
    wrong = client.post(
        f"{PUB}/claims/status", json={"reference": reference, "phone": "9111111111"}
    )
    assert wrong.status_code in (403, 404)
