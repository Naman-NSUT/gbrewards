"""The dealer app's home-screen carousel.

Reads the worker programme's `banners` table on purpose — one poster, published
once, shown in both apps. What matters is that reusing the rows did not reuse
the AUDIENCE: the worker list endpoint takes a broker token, and this one must
take a dealer token and nothing else.
"""

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from app.models.banner import Banner
from tests.dealer.factories import make_dealer, make_staff


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


def _banner(db, caption: str, order: int, active: bool = True) -> Banner:
    b = Banner(
        image_url=f"/api/v1/catalog/banners/{order}/image",
        caption=caption,
        sort_order=order,
        is_active=active,
    )
    db.add(b)
    db.flush()
    return b


@pytest.fixture
def staff_headers(db):  # type: ignore[no-untyped-def]
    dealer = make_dealer(db)
    dealer.status = "active"
    staff = make_staff(db, dealer)
    db.commit()
    token = create_access_token(str(staff.id), "dealer", {"dealer_id": str(dealer.id)})
    return {"Authorization": f"Bearer {token}"}


def test_the_carousel_returns_active_banners_in_back_office_order(client, db, staff_headers):
    _banner(db, "Second", 2)
    _banner(db, "First", 1)
    db.commit()

    resp = client.get("/api/v1/dealer/banners", headers=staff_headers)

    assert resp.status_code == 200, resp.text
    assert [b["caption"] for b in resp.json()] == ["First", "Second"]


def test_a_retired_banner_does_not_reappear_in_the_dealer_app(client, db, staff_headers):
    """Unpublishing in the back office has to unpublish it everywhere."""
    _banner(db, "Live", 1)
    _banner(db, "Retired", 2, active=False)
    db.commit()

    captions = [
        b["caption"] for b in client.get("/api/v1/dealer/banners", headers=staff_headers).json()
    ]
    assert captions == ["Live"]


def test_the_carousel_needs_a_dealer_token(client):
    assert client.get("/api/v1/dealer/banners").status_code == 401


def test_a_worker_token_cannot_read_the_dealer_carousel(client, db):
    """Sharing the table must not have shared the audience."""
    _banner(db, "Live", 1)
    db.commit()
    token = create_access_token("00000000-0000-4000-8000-000000000001", "broker")

    resp = client.get("/api/v1/dealer/banners", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
