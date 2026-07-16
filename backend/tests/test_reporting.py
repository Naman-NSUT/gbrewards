from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry
from app.models.redemption_request import RedemptionRequest
from app.services.claim import claim
from app.services.ledger import LedgerType
from tests.factories import admin_headers, make_admin, make_product, make_unit, make_user


def test_dashboard_tiles(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    product = make_product(db, points_value=100)
    u1 = make_user(db, phone="+919900100001")
    u2 = make_user(db, phone="+919900100002")
    unit1 = make_unit(db, product=product)
    unit2 = make_unit(db, product=product)
    db.flush()
    claim(db, user_id=u1.id, token=unit1.token)
    claim(db, user_id=u2.id, token=unit2.token)
    # a pending redemption
    from app.models.redemption_request import RedemptionRequest

    db.add(RedemptionRequest(user_id=u1.id, points=10, status="pending"))
    # a backdated scan_credit (counts in total, not today/week)
    old = make_unit(db, product=product, status="claimed")
    db.add(
        LedgerEntry(
            user_id=u2.id,
            amount=100,
            type=str(LedgerType.SCAN_CREDIT),
            product_unit_id=old.id,
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
    )
    db.commit()

    r = client.get("/api/v1/admin/dashboard", headers=admin_headers(admin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_users"] == 2
    assert body["total_points_outstanding"] == 300  # 100 + 100 + 100 backdated
    assert body["total_scans"] == 3
    assert body["scans_today"] == 2  # backdated one excluded
    assert body["scans_this_week"] == 2
    assert body["pending_redemptions"] == 1
    assert body["products_in_catalog"] == 1


def test_scans_feed_filters_and_pagination(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    pa = make_product(db, name="A", points_value=10)
    pb = make_product(db, name="B", points_value=20)
    u1 = make_user(db, phone="+919900200001")
    u2 = make_user(db, phone="+919900200002")
    units_a = [make_unit(db, product=pa) for _ in range(3)]
    unit_b = make_unit(db, product=pb)
    db.flush()
    for un in units_a:
        claim(db, user_id=u1.id, token=un.token)
    claim(db, user_id=u2.id, token=unit_b.token)
    db.commit()
    h = admin_headers(admin)

    # filter by product
    r = client.get(f"/api/v1/admin/scans?product_id={pa.id}", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 3
    assert all(i["product"]["id"] == str(pa.id) for i in items)

    # filter by user — and the scanned QR token is surfaced
    r = client.get(f"/api/v1/admin/scans?user_id={u2.id}", headers=h)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["token"] == unit_b.token

    # pagination
    r = client.get("/api/v1/admin/scans?limit=2", headers=h)
    body = r.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None
    r2 = client.get(f"/api/v1/admin/scans?limit=2&cursor={body['next_cursor']}", headers=h)
    assert len(r2.json()["items"]) == 2  # 4 total → 2 + 2


def test_analytics(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    pa = make_product(db, name="Alpha", points_value=10)
    pb = make_product(db, name="Beta", points_value=20)
    u1 = make_user(db, phone="+919900400001")
    u2 = make_user(db, phone="+919900400002")
    # 3 claims on Alpha (today), 1 on Beta
    units_a = [make_unit(db, product=pa) for _ in range(3)]
    unit_b = make_unit(db, product=pb)
    db.flush()
    for un in units_a:
        claim(db, user_id=u1.id, token=un.token)
    claim(db, user_id=u2.id, token=unit_b.token)
    # redemptions in mixed statuses
    db.add_all(
        [
            RedemptionRequest(user_id=u1.id, points=5, status="pending"),
            RedemptionRequest(user_id=u1.id, points=5, status="approved"),
        ]
    )
    # a backdated scan_credit (5 days ago) — should land in its own day bucket
    old_unit = make_unit(db, product=pb, status="claimed")
    db.add(
        LedgerEntry(
            user_id=u2.id,
            amount=10,
            type=str(LedgerType.SCAN_CREDIT),
            product_unit_id=old_unit.id,
            created_at=datetime.now(UTC) - timedelta(days=5),
        )
    )
    db.commit()

    r = client.get("/api/v1/admin/analytics", headers=admin_headers(admin))
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["scans_by_day"]) == 14
    assert body["scans_by_day"][-1]["scans"] == 4  # today's 4 claims
    assert body["scans_by_day"][-6]["scans"] == 1  # backdated one, 5 days ago

    assert body["redemptions_by_status"]["pending"] == 1
    assert body["redemptions_by_status"]["approved"] == 1

    # Alpha (3 claimed) ranks above Beta (1 claimed)
    names = [p["name"] for p in body["top_products"]]
    assert names[0] == "Alpha"
    assert body["top_products"][0]["claimed"] == 3


def test_audit_feed_filters(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    unit = make_unit(db, status="active")
    db.commit()
    h = admin_headers(admin)

    # generate audit rows via real admin actions
    client.post(f"/api/v1/admin/users/{user.id}/credit", headers=h, json={"points": 5})
    client.post(f"/api/v1/admin/units/{unit.id}/void", headers=h)

    r = client.get("/api/v1/admin/audit", headers=h)
    assert r.status_code == 200
    actions = {i["action"] for i in r.json()["items"]}
    assert {"credit", "void_unit"} <= actions

    # filter by entity
    r = client.get("/api/v1/admin/audit?entity=user", headers=h)
    assert all(i["entity_type"] == "user" for i in r.json()["items"])
    assert any(i["action"] == "credit" for i in r.json()["items"])

    r = client.get("/api/v1/admin/audit?entity=product_unit", headers=h)
    assert all(i["entity_type"] == "product_unit" for i in r.json()["items"])

    # filter by actor
    r = client.get(f"/api/v1/admin/audit?actor={admin.id}", headers=h)
    assert len(r.json()["items"]) >= 2
