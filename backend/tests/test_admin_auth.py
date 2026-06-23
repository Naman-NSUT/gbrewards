from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    admin_headers,
    auth_headers,
    make_admin,
    make_user,
)


def test_login_success(client: TestClient, db: Session) -> None:
    make_admin(db, email="boss@example.com", password="s3cret123")
    db.commit()
    r = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "boss@example.com", "password": "s3cret123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["admin"]["email"] == "boss@example.com"


def test_login_bad_password(client: TestClient, db: Session) -> None:
    make_admin(db, email="boss2@example.com", password="right-pass")
    db.commit()
    r = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "boss2@example.com", "password": "wrong-pass"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_broker_token_rejected_on_admin_route(client: TestClient, db: Session) -> None:
    user = make_user(db)
    db.commit()
    r = client.get("/api/v1/admin/products", headers=auth_headers(user))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_admin_token_rejected_on_broker_route(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.get("/api/v1/me", headers=admin_headers(admin))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"
