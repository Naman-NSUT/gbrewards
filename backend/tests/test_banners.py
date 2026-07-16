import io
import uuid

from fastapi.testclient import TestClient
from PIL import Image
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


def _img_bytes(fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (24, 12), (200, 50, 50)).save(buf, format=fmt)
    return buf.getvalue()


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


def test_admin_create_banner_from_upload_writes_audit(
    client: TestClient, db: Session
) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.post(
        "/api/v1/admin/banners",
        headers=admin_headers(admin),
        data={"caption": "Promo", "sort_order": "3"},
        files={"image": ("promo.png", _img_bytes(), "image/png")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # uploaded image is stored in the DB and served via the catalog endpoint
    assert body["image_url"].startswith("/api/v1/catalog/banners/")
    assert body["image_url"].endswith("/image")
    assert body["caption"] == "Promo"
    assert body["is_active"] is True
    assert body["sort_order"] == 3
    assert _audit_count(db, "create_banner") == 1


def test_uploaded_banner_image_served_publicly(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    created = client.post(
        "/api/v1/admin/banners",
        headers=admin_headers(admin),
        data={"caption": "Pic"},
        files={"image": ("p.png", _img_bytes(), "image/png")},
    )
    assert created.status_code == 201, created.text
    url = created.json()["image_url"]
    # public — served with NO auth header (so the mobile <Image> can load it),
    # re-encoded to optimised JPEG
    img = client.get(url)
    assert img.status_code == 200, img.text
    assert img.headers["content-type"] == "image/jpeg"
    assert len(img.content) > 0


def test_admin_create_banner_rejects_non_image(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.post(
        "/api/v1/admin/banners",
        headers=admin_headers(admin),
        data={"caption": "Bad"},
        files={"image": ("note.txt", b"not an image", "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_image"


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
        data={"is_active": "false", "caption": "Updated"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    assert r.json()["caption"] == "Updated"
    assert _audit_count(db, "update_banner") == 1


def test_admin_update_banner_unknown_404(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.patch(
        f"/api/v1/admin/banners/{uuid.uuid4()}",
        headers=admin_headers(admin),
        data={"sort_order": "1"},
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
