"""A customer must be able to find and claim a warranty that has no serial.

Registration moved from scanning a label to picking a product and typing an
invoice number, so warranties created since have `serial = NULL`. Both public
customer paths were keyed on the serial:

  POST /public/lookup   { serial }          -> "no warranty found"
  POST /public/claims   { serial, phone }   -> could never match

The claim path is the one that matters. A five-year warranty exists so that it
can be claimed against; a customer who cannot raise a claim does not have one.
Both now match a serial OR an invoice number, case-insensitively for the invoice
because that is how the uniqueness index issued it.
"""

import uuid

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.dealer.services import registration
from tests.dealer.factories import make_dealer, make_product, make_rate, make_staff


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    from app.main import create_app

    app = create_app()

    def _get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fakeredis.FakeRedis(decode_responses=True)
    with TestClient(app) as c:
        yield c


PHONE = "+919812345678"


@pytest.fixture
def sale(db):  # type: ignore[no-untyped-def]
    """A warranty registered the new way: a product, an invoice, no serial."""
    dealer = make_dealer(db)
    dealer.status = "active"
    staff = make_staff(db, dealer)
    product = make_product(db, name="HR Foam 6 inch", months=60)
    make_rate(db, 120, product=product)
    db.commit()

    invoice = f"INV-{uuid.uuid4().hex[:6].upper()}"
    result = registration.register(
        db,
        staff=staff,
        product_id=product.id,
        invoice_ref=invoice,
        customer_phone=PHONE,
        customer_name="Asha Menon",
    )
    db.commit()
    assert result.warranty.serial is None, "the new flow must not invent a serial"
    return result.warranty, invoice


def test_a_customer_can_look_up_a_warranty_by_its_invoice_number(client, sale):
    _warranty, invoice = sale

    resp = client.post("/api/v1/public/lookup", json={"serial": invoice})

    assert resp.status_code == 200, resp.text
    assert len(resp.json()["results"]) == 1


def test_the_invoice_number_is_matched_case_insensitively(client, sale):
    """The bill is typed by hand; the index that issued it compares lower()."""
    _warranty, invoice = sale

    resp = client.post("/api/v1/public/lookup", json={"serial": invoice.lower()})

    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


def test_a_customer_can_raise_a_claim_with_their_invoice_number(client, sale):
    """The regression: without this, every post-change customer is unclaimable."""
    _warranty, invoice = sale

    resp = client.post(
        "/api/v1/public/claims",
        json={
            "serial": invoice,
            "phone": PHONE,
            "description": "The foam has sagged badly on one side after four months.",
        },
    )

    assert resp.status_code in (200, 201), resp.text


def test_the_claim_still_needs_the_phone_on_the_record(client, sale):
    """The possession check survives: an invoice number alone is not a secret."""
    _warranty, invoice = sale

    resp = client.post(
        "/api/v1/public/claims",
        json={
            "serial": invoice,
            "phone": "+919800000000",
            "description": "Trying to claim against someone else's warranty entirely.",
        },
    )

    assert resp.status_code == 404


def test_a_serial_still_works_for_warranties_that_have_one(client, db):
    """Historic rows keep their serial, and support is still asked about them."""
    from app.dealer.models.customer import Customer
    from app.dealer.models.warranty import Warranty
    from app.dealer.services.warranty_dates import business_today

    dealer = make_dealer(db)
    customer = Customer(phone=PHONE, name="Old Customer")
    db.add(customer)
    db.flush()
    db.add(
        Warranty(
            # Stored lowercase, as normalise_serial() writes them — the printed
            # label is a bare UUID and a human retyping it will not match case.
            serial="7b3d9f21-4c1e-4a88-9f02-6de41b7c5a30",
            warranty_months=60,
            dealer_id=dealer.id,
            customer_id=customer.id,
            warranty_start_date=business_today(),
            warranty_end_date=business_today().replace(year=business_today().year + 5),
            status="active",
            source="dealer",
        )
    )
    db.commit()

    # Typed back in upper case, exactly as a customer would from a scuffed label.
    resp = client.post(
        "/api/v1/public/lookup", json={"serial": "7B3D9F21-4C1E-4A88-9F02-6DE41B7C5A30"}
    )
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1
