from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from tests.factories import (
    admin_headers,
    auth_headers,
    make_admin,
    make_reward,
    make_user,
)


def _audit_count(db: Session, action: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    ).scalar_one()


def test_create_reward_writes_audit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    r = client.post(
        "/api/v1/admin/rewards",
        headers=admin_headers(admin),
        json={"title": "T-Shirt", "points_cost": 120, "sort_order": 2},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "T-Shirt"
    assert body["points_cost"] == 120
    assert body["is_active"] is True
    assert _audit_count(db, "create_reward") == 1


def test_list_rewards_includes_inactive_ordered(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    make_reward(db, title="B", sort_order=1, is_active=False)
    make_reward(db, title="A", sort_order=0)
    db.commit()
    r = client.get("/api/v1/admin/rewards", headers=admin_headers(admin))
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()]
    assert titles == ["A", "B"]


def test_update_reward_writes_audit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    reward = make_reward(db)
    db.commit()
    r = client.patch(
        f"/api/v1/admin/rewards/{reward.id}",
        headers=admin_headers(admin),
        json={"points_cost": 999},
    )
    assert r.status_code == 200
    assert r.json()["points_cost"] == 999
    assert _audit_count(db, "update_reward") == 1


def test_update_reward_unknown_404(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    db.commit()
    import uuid

    r = client.patch(
        f"/api/v1/admin/rewards/{uuid.uuid4()}",
        headers=admin_headers(admin),
        json={"points_cost": 1},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "reward_not_found"


def test_delete_unreferenced_reward(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    reward = make_reward(db)
    db.commit()
    r = client.delete(f"/api/v1/admin/rewards/{reward.id}", headers=admin_headers(admin))
    assert r.status_code == 204
    assert _audit_count(db, "delete_reward") == 1


def test_delete_referenced_reward_blocked(client: TestClient, db: Session) -> None:
    from app.services import ledger
    from app.services.ledger import LedgerType

    admin = make_admin(db)
    user = make_user(db)
    reward = make_reward(db, points_cost=10)
    ledger.add_entry(db, user_id=user.id, amount=100, type=LedgerType.ADMIN_CREDIT)
    db.commit()

    # create a reward-backed redemption referencing this reward
    client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"reward_id": str(reward.id)},
    )
    r = client.delete(f"/api/v1/admin/rewards/{reward.id}", headers=admin_headers(admin))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "reward_in_use"


def test_broker_token_rejected_on_admin_rewards(client: TestClient, db: Session) -> None:
    user = make_user(db)
    db.commit()
    r = client.get("/api/v1/admin/rewards", headers=auth_headers(user))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"
