"""The product list the app's registration dropdown is built from.

Scanning identified the mattress, so the app never needed a catalogue. Choosing
a product means it does, and no endpoint a `dealer` token could read existed:
/dealer-admin/products is the back office and /products belongs to the worker
programme. These pin the two things that matter — the right audience, and that
a product the back office retired cannot be sold.
"""

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from tests.dealer.factories import make_dealer, make_product, make_staff


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


@pytest.fixture
def staff_headers(db):  # type: ignore[no-untyped-def]
    dealer = make_dealer(db)
    dealer.status = "active"
    staff = make_staff(db, dealer)
    db.commit()
    token = create_access_token(str(staff.id), "dealer", {"dealer_id": str(dealer.id)})
    return {"Authorization": f"Bearer {token}"}


def test_the_dropdown_lists_active_products_by_name(client, db, staff_headers):
    make_product(db, name="Ortho Bonnell 8 inch", months=36)
    make_product(db, name="HR Foam 6 inch", months=60)
    db.commit()

    resp = client.get("/api/v1/dealer/products", headers=staff_headers)

    assert resp.status_code == 200, resp.text
    names = [p["name"] for p in resp.json()]
    assert names == ["HR Foam 6 inch", "Ortho Bonnell 8 inch"], "sorted for a human scanning a list"


def test_a_retired_product_cannot_be_sold(client, db, staff_headers):
    """Filtered server-side: an offerable product is a sellable one."""
    make_product(db, name="Current", months=60)
    gone = make_product(db, name="Discontinued", months=60)
    gone.is_active = False
    db.commit()

    names = [p["name"] for p in client.get("/api/v1/dealer/products", headers=staff_headers).json()]
    assert names == ["Current"]


def test_the_cover_length_is_included(client, db, staff_headers):
    """A 36-month model and a 60-month one must be distinguishable at the counter."""
    make_product(db, name="Ortho Bonnell 8 inch", months=36)
    db.commit()

    item = client.get("/api/v1/dealer/products", headers=staff_headers).json()[0]
    assert item["warranty_months"] == 36
    assert set(item) == {"id", "name", "model_code", "warranty_months"}, (
        "lean on purpose — terms are label copy and is_active is a back-office concern"
    )


def test_the_catalogue_needs_a_dealer_token(client):
    assert client.get("/api/v1/dealer/products").status_code == 401


def test_a_worker_token_cannot_read_the_dealer_catalogue(client, db):
    make_product(db, name="HR Foam 6 inch", months=60)
    db.commit()
    token = create_access_token("00000000-0000-4000-8000-000000000001", "broker")

    resp = client.get("/api/v1/dealer/products", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
