import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry
from app.services import ledger
from app.services.ledger import LedgerType
from tests.factories import (
    admin_headers,
    auth_headers,
    make_admin,
    make_reward,
    make_user,
)


def _give(db: Session, user_id: uuid.UUID, amount: int) -> None:
    ledger.add_entry(db, user_id=user_id, amount=amount, type=LedgerType.ADMIN_CREDIT)


def test_reward_redemption_holds_points_cost(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=30)
    _give(db, user.id, 100)
    db.commit()

    r = client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"reward_id": str(reward.id)},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["points"] == 30
    assert body["reward_id"] == str(reward.id)

    # pending hold reduces available by points_cost; balance unchanged
    assert ledger.balance(db, user.id) == 100
    assert ledger.available(db, user.id) == 70


def test_reward_redemption_approve_debits_and_sets_reward(
    client: TestClient, db: Session
) -> None:
    admin = make_admin(db)
    user = make_user(db)
    reward = make_reward(db, points_cost=40)
    _give(db, user.id, 100)
    db.commit()

    rid = client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"reward_id": str(reward.id)},
    ).json()["id"]

    r = client.post(
        f"/api/v1/admin/redemptions/{rid}/approve", headers=admin_headers(admin), json={}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assert r.json()["reward_id"] == str(reward.id)
    assert r.json()["reward"] == {"id": str(reward.id), "title": reward.title}

    debits = list(
        db.execute(
            select(LedgerEntry).where(
                LedgerEntry.user_id == user.id,
                LedgerEntry.type == "redemption_debit",
            )
        ).scalars()
    )
    assert len(debits) == 1
    assert debits[0].amount == -40
    assert str(debits[0].redemption_id) == rid


def test_reward_redemption_insufficient_balance(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=200)
    _give(db, user.id, 50)
    db.commit()
    r = client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"reward_id": str(reward.id)},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "insufficient_balance"


def test_inactive_reward_rejected(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=10, is_active=False)
    _give(db, user.id, 100)
    db.commit()
    r = client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"reward_id": str(reward.id)},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "reward_inactive"


def test_unknown_reward_rejected(client: TestClient, db: Session) -> None:
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()
    r = client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"reward_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "reward_not_found"


def test_neither_points_nor_reward_rejected(client: TestClient, db: Session) -> None:
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()
    r = client.post("/api/v1/redemptions", headers=auth_headers(user), json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_both_points_and_reward_rejected(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=10)
    _give(db, user.id, 100)
    db.commit()
    r = client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"points": 10, "reward_id": str(reward.id)},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_generic_redemption_still_works(client: TestClient, db: Session) -> None:
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()
    r = client.post("/api/v1/redemptions", headers=auth_headers(user), json={"points": 25})
    assert r.status_code == 201
    assert r.json()["reward_id"] is None
