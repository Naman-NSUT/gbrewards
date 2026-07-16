import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from tests.factories import (
    admin_headers,
    auth_headers,
    make_admin,
    make_banner,
    make_user,
)


def _audit_count(db: Session, action: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    ).scalar_one()


def test_broker_banners_active_only_ordered(client: TestClient, db: Session) -> None:
    user = make_user(db)
    make_banner(db, caption="Second", sort_order=1)
    make_banner(db, caption="First", sort_order=0)
    make_banner(db, caption="Hidden", is_active=False, sort_order=0)
    db.commit()
    r = client.get("/api/v1/catalog/banners", headers=auth_headers(user))
    assert r.status_code == 200, r.text
    captions = [x["caption"] for x in r.json()]
    assert captions == ["First", "Second"]
    # relative image_urls are returned verbatim for the client to resolve
    assert r.json()[0]["image_url"] == "/static/banners/goodbed-poster.jpg"


def test_admin_create_banner_writes_audit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.post(
        "/api/v1/admin/banners",
        headers=admin_headers(admin),
        json={
            "image_url": "https://cdn.example.com/promo.jpg",
            "caption": "Promo",
            "sort_order": 3,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["image_url"] == "https://cdn.example.com/promo.jpg"
    assert body["caption"] == "Promo"
    assert body["is_active"] is True
    assert body["sort_order"] == 3
    assert _audit_count(db, "create_banner") == 1


def test_admin_list_banners_includes_inactive_ordered(
    client: TestClient, db: Session
) -> None:
    admin = make_admin(db)
    make_banner(db, caption="B", sort_order=1, is_active=False)
    make_banner(db, caption="A", sort_order=0)
    db.commit()
    r = client.get("/api/v1/admin/banners", headers=admin_headers(admin))
    assert r.status_code == 200
    captions = [x["caption"] for x in r.json()]
    assert captions == ["A", "B"]


def test_admin_update_banner_writes_audit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    banner = make_banner(db)
    db.commit()
    r = client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        json={"is_active": False, "caption": "Updated"},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert r.json()["caption"] == "Updated"
    assert _audit_count(db, "update_banner") == 1


def test_admin_update_banner_unknown_404(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.patch(
        f"/api/v1/admin/banners/{uuid.uuid4()}",
        headers=admin_headers(admin),
        json={"sort_order": 1},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "banner_not_found"


def test_admin_delete_banner_writes_audit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    banner = make_banner(db)
    db.commit()
    r = client.delete(
        f"/api/v1/admin/banners/{banner.id}", headers=admin_headers(admin)
    )
    assert r.status_code == 204
    assert _audit_count(db, "delete_banner") == 1


def test_broker_token_rejected_on_admin_banners(
    client: TestClient, db: Session
) -> None:
    user = make_user(db)
    db.commit()
    r = client.get("/api/v1/admin/banners", headers=auth_headers(user))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_admin_token_rejected_on_broker_banners(
    client: TestClient, db: Session
) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.get("/api/v1/catalog/banners", headers=admin_headers(admin))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"
