from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    admin_headers,
    auth_headers,
    make_admin,
    make_content_doc,
    make_faq,
    make_product,
    make_reward,
    make_user,
)


def test_broker_products_active_only(client: TestClient, db: Session) -> None:
    user = make_user(db)
    make_product(db, name="Active", points_value=10)
    inactive = make_product(db, name="Inactive", points_value=5)
    inactive.is_active = False
    db.commit()
    r = client.get("/api/v1/products", headers=auth_headers(user))
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert names == ["Active"]
    # narrowed projection
    assert set(r.json()[0].keys()) == {"id", "name", "points_value"}


def test_broker_rewards_active_only_ordered(client: TestClient, db: Session) -> None:
    user = make_user(db)
    make_reward(db, title="Zeta", sort_order=0)
    make_reward(db, title="Alpha", sort_order=0)
    make_reward(db, title="Hidden", is_active=False)
    db.commit()
    r = client.get("/api/v1/rewards", headers=auth_headers(user))
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()]
    assert titles == ["Alpha", "Zeta"]


def test_broker_faqs_published_only(client: TestClient, db: Session) -> None:
    user = make_user(db)
    make_faq(db, question="Shown", is_published=True)
    make_faq(db, question="Draft", is_published=False)
    db.commit()
    r = client.get("/api/v1/faqs", headers=auth_headers(user))
    assert r.status_code == 200
    questions = [x["question"] for x in r.json()]
    assert questions == ["Shown"]
    assert "is_published" not in r.json()[0]


def test_broker_content_by_key(client: TestClient, db: Session) -> None:
    user = make_user(db)
    make_content_doc(db, key="privacy", title="Privacy", body="text")
    db.commit()
    r = client.get("/api/v1/content/privacy", headers=auth_headers(user))
    assert r.status_code == 200
    assert r.json()["key"] == "privacy"
    r = client.get("/api/v1/content/missing", headers=auth_headers(user))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "content_not_found"


def test_admin_token_rejected_on_broker_catalog(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    for route in ["/api/v1/products", "/api/v1/rewards", "/api/v1/faqs"]:
        r = client.get(route, headers=admin_headers(admin))
        assert r.status_code == 401, route
        assert r.json()["error"]["code"] == "invalid_token"
