import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from tests.factories import (
    admin_headers,
    auth_headers,
    make_admin,
    make_content_doc,
    make_faq,
    make_user,
)


def _audit_count(db: Session, action: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    ).scalar_one()


def test_faq_crud_and_audit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    h = admin_headers(admin)

    r = client.post(
        "/api/v1/admin/faqs",
        headers=h,
        json={"question": "Q1", "answer": "A1", "sort_order": 1},
    )
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    assert _audit_count(db, "create_faq") == 1

    r = client.patch(f"/api/v1/admin/faqs/{fid}", headers=h, json={"is_published": False})
    assert r.status_code == 200
    assert r.json()["is_published"] is False
    assert _audit_count(db, "update_faq") == 1

    r = client.delete(f"/api/v1/admin/faqs/{fid}", headers=h)
    assert r.status_code == 204
    assert _audit_count(db, "delete_faq") == 1


def test_faq_unknown_404(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.patch(
        f"/api/v1/admin/faqs/{uuid.uuid4()}",
        headers=admin_headers(admin),
        json={"answer": "x"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "faq_not_found"


def test_content_upsert_inserts_then_updates(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    h = admin_headers(admin)

    r = client.put(
        "/api/v1/admin/content/terms",
        headers=h,
        json={"title": "Terms", "body": "v1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["key"] == "terms"
    assert r.json()["body"] == "v1"
    assert _audit_count(db, "update_content") == 1

    # upsert same key updates in place (no duplicate row)
    r = client.put(
        "/api/v1/admin/content/terms",
        headers=h,
        json={"title": "Terms", "body": "v2"},
    )
    assert r.status_code == 200
    assert r.json()["body"] == "v2"
    assert len(client.get("/api/v1/admin/content", headers=h).json()) == 1
    assert _audit_count(db, "update_content") == 2


def test_content_get_unknown_404(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.get("/api/v1/admin/content/nope", headers=admin_headers(admin))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "content_not_found"


def test_broker_token_rejected_on_admin_content(client: TestClient, db: Session) -> None:
    user = make_user(db)
    make_content_doc(db)
    make_faq(db)
    db.commit()
    for route in ["/api/v1/admin/faqs", "/api/v1/admin/content"]:
        r = client.get(route, headers=auth_headers(user))
        assert r.status_code == 401, route
        assert r.json()["error"]["code"] == "invalid_token"
