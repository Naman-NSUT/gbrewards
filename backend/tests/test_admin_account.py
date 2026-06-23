from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_secret
from app.models.admin import Admin
from tests.factories import admin_headers, make_admin


def test_get_and_update_profile(client: TestClient, db: Session) -> None:
    admin = make_admin(db, email="boss@example.com")
    db.commit()
    h = admin_headers(admin)

    r = client.get("/api/v1/admin/me", headers=h)
    assert r.status_code == 200
    assert r.json()["email"] == "boss@example.com"

    r = client.patch("/api/v1/admin/me", headers=h, json={"name": "New Name", "email": "newid"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "New Name"
    assert r.json()["email"] == "newid"


def test_email_must_be_unique(client: TestClient, db: Session) -> None:
    a1 = make_admin(db, email="one@example.com")
    make_admin(db, email="two@example.com")
    db.commit()
    r = client.patch(
        "/api/v1/admin/me", headers=admin_headers(a1), json={"email": "two@example.com"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_change_password(client: TestClient, db: Session) -> None:
    admin = make_admin(db, password="oldpass123")
    db.commit()
    h = admin_headers(admin)

    # wrong current password
    r = client.post(
        "/api/v1/admin/me/password",
        headers=h,
        json={"current_password": "nope", "new_password": "brandnew123"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"

    # correct
    r = client.post(
        "/api/v1/admin/me/password",
        headers=h,
        json={"current_password": "oldpass123", "new_password": "brandnew123"},
    )
    assert r.status_code == 204
    db.expire_all()
    refreshed = db.get(Admin, admin.id)
    assert refreshed is not None
    assert verify_secret(refreshed.password_hash, "brandnew123")

    # too-short new password rejected
    r = client.post(
        "/api/v1/admin/me/password",
        headers=h,
        json={"current_password": "brandnew123", "new_password": "short"},
    )
    assert r.status_code == 422
