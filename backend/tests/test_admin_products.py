from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.product_unit import ProductUnit
from app.services.claim import claim
from tests.factories import admin_headers, make_admin, make_user


def _audit_count(db: Session, action: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    ).scalar_one()


def test_product_crud_and_counts(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    h = admin_headers(admin)

    # create
    r = client.post(
        "/api/v1/admin/products",
        headers=h,
        json={"name": "Widget", "points_value": 100},
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert _audit_count(db, "create_product") == 1

    # list
    r = client.get("/api/v1/admin/products", headers=h)
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    # patch
    r = client.patch(f"/api/v1/admin/products/{pid}", headers=h, json={"points_value": 150})
    assert r.status_code == 200
    assert r.json()["points_value"] == 150

    # batch of 5 → 5 active units
    r = client.post(
        f"/api/v1/admin/products/{pid}/batches",
        headers=h,
        json={"quantity": 5, "label": "Jan batch"},
    )
    assert r.status_code == 201, r.text
    units = list(db.execute(select(ProductUnit).where(ProductUnit.product_id == pid)).scalars())
    assert len(units) == 5
    assert all(u.status == "active" for u in units)

    # counts
    r = client.get(f"/api/v1/admin/products/{pid}", headers=h)
    counts = r.json()
    assert counts["units_generated"] == 5
    assert counts["units_available"] == 5
    assert counts["units_claimed"] == 0

    # claim one, counts shift
    user = make_user(db)
    db.flush()
    claim(db, user_id=user.id, token=units[0].token)
    r = client.get(f"/api/v1/admin/products/{pid}", headers=h)
    counts = r.json()
    assert counts["units_claimed"] == 1
    assert counts["units_available"] == 4


def test_void_unit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    db.commit()
    h = admin_headers(admin)

    r = client.post("/api/v1/admin/products", headers=h, json={"name": "P", "points_value": 10})
    pid = r.json()["id"]
    client.post(f"/api/v1/admin/products/{pid}/batches", headers=h, json={"quantity": 2})
    units = list(db.execute(select(ProductUnit).where(ProductUnit.product_id == pid)).scalars())

    # void an active unit
    r = client.post(f"/api/v1/admin/units/{units[0].id}/void", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "void"
    assert _audit_count(db, "void_unit") == 1

    # claim the other, then void → rejected
    claim(db, user_id=user.id, token=units[1].token)
    r = client.post(f"/api/v1/admin/units/{units[1].id}/void", headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "cannot_void_claimed"


def test_delete_product(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    h = admin_headers(admin)

    # a fresh product with no units can be deleted
    pid = client.post(
        "/api/v1/admin/products", headers=h, json={"name": "Deletable", "points_value": 10}
    ).json()["id"]
    r = client.delete(f"/api/v1/admin/products/{pid}", headers=h)
    assert r.status_code == 204
    assert client.get(f"/api/v1/admin/products/{pid}", headers=h).status_code == 404
    assert _audit_count(db, "delete_product") == 1

    # a product with generated QR units cannot be deleted
    pid2 = client.post(
        "/api/v1/admin/products", headers=h, json={"name": "InUse", "points_value": 10}
    ).json()["id"]
    client.post(f"/api/v1/admin/products/{pid2}/batches", headers=h, json={"quantity": 2})
    r = client.delete(f"/api/v1/admin/products/{pid2}", headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "product_in_use"


def test_unit_lookup_with_history(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    db.commit()
    h = admin_headers(admin)

    r = client.post("/api/v1/admin/products", headers=h, json={"name": "P2", "points_value": 30})
    pid = r.json()["id"]
    client.post(f"/api/v1/admin/products/{pid}/batches", headers=h, json={"quantity": 1})
    unit = db.execute(select(ProductUnit).where(ProductUnit.product_id == pid)).scalar_one()
    claim(db, user_id=user.id, token=unit.token)

    r = client.get(f"/api/v1/admin/units/{unit.token}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "claimed"
    assert len(body["history"]) == 1
    assert body["history"][0]["type"] == "scan_credit"
