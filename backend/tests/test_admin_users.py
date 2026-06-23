from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.ledger_entry import LedgerEntry
from app.services import ledger
from app.services.claim import claim
from app.services.ledger import LedgerType
from tests.factories import (
    admin_headers,
    auth_headers,
    make_admin,
    make_product,
    make_unit,
    make_user,
)


def _audit_count(db: Session, action: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    ).scalar_one()


def test_list_users_with_balance_and_earned(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db, name="Alice")
    product = make_product(db, points_value=100)
    unit = make_unit(db, product=product)
    db.flush()
    claim(db, user_id=user.id, token=unit.token)
    ledger.add_entry(db, user_id=user.id, amount=-40, type=LedgerType.ADMIN_DEBIT)
    db.commit()

    r = client.get("/api/v1/admin/users", headers=admin_headers(admin))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    row = next(i for i in items if i["id"] == str(user.id))
    assert row["balance"] == 60
    assert row["total_earned"] == 100  # only the positive scan_credit counts


def test_get_user_detail(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    db.commit()
    r = client.get(f"/api/v1/admin/users/{user.id}", headers=admin_headers(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(user.id)
    assert body["balance"] == 0
    assert body["available"] == 0


def test_credit_and_debit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    db.commit()
    h = admin_headers(admin)

    r = client.post(
        f"/api/v1/admin/users/{user.id}/credit", headers=h, json={"points": 50, "note": "bonus"}
    )
    assert r.status_code == 200
    assert r.json()["balance"] == 50
    assert _audit_count(db, "credit") == 1

    r = client.post(
        f"/api/v1/admin/users/{user.id}/debit", headers=h, json={"points": 80, "note": "correction"}
    )
    assert r.status_code == 200
    # D3: negative balance allowed
    assert r.json()["balance"] == -30
    assert _audit_count(db, "debit") == 1

    # ledger has both adjustment rows
    count = db.execute(
        select(func.count()).select_from(LedgerEntry).where(LedgerEntry.user_id == user.id)
    ).scalar_one()
    assert count == 2


def test_adjust_rejects_non_positive(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    db.commit()
    h = admin_headers(admin)
    r = client.post(f"/api/v1/admin/users/{user.id}/credit", headers=h, json={"points": 0})
    assert r.status_code == 422


def test_disable_user_blocks_broker(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    db.commit()

    r = client.patch(
        f"/api/v1/admin/users/{user.id}", headers=admin_headers(admin), json={"is_active": False}
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert _audit_count(db, "update_user") == 1

    # disabled broker can no longer use their token
    r = client.get("/api/v1/me", headers=auth_headers(user))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "user_disabled"


def test_user_ledger_drilldown(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    db.flush()
    for i in range(3):
        ledger.add_entry(db, user_id=user.id, amount=10 + i, type=LedgerType.ADMIN_CREDIT)
    db.commit()

    r = client.get(f"/api/v1/admin/users/{user.id}/ledger?limit=2", headers=admin_headers(admin))
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None

    r2 = client.get(
        f"/api/v1/admin/users/{user.id}/ledger?limit=2&cursor={body['next_cursor']}",
        headers=admin_headers(admin),
    )
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1


def test_unknown_user_404(client: TestClient, db: Session) -> None:
    import uuid

    admin = make_admin(db)
    db.commit()
    r = client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=admin_headers(admin))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "user_not_found"
