"""Redeeming several of one reward in a single request.

A reward is priced per unit — "Cash 500, 50 pts" — and a worker sitting on 300
points wants six of them, not six separate requests. The slider in the app sends
a quantity; these pin what the server must do with it.

The important ones are the refusals. The quantity multiplies the points that get
held, so it is the one field a client can send that scales what it costs the
programme, and the hold is what stops a balance being spent twice.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.redemption_request import RedemptionRequest
from app.services import ledger, redemption
from app.services.ledger import LedgerType
from tests.factories import admin_headers, auth_headers, make_admin, make_reward, make_user


def _give(db: Session, user_id: uuid.UUID, amount: int) -> None:
    ledger.add_entry(db, user_id=user_id, amount=amount, type=LedgerType.ADMIN_CREDIT)


def _redeem(client: TestClient, user, reward, **extra):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/redemptions",
        headers=auth_headers(user),
        json={"reward_id": str(reward.id), **extra},
    )


def test_three_of_a_reward_costs_three_times_the_points(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, title="Cash 500", points_cost=50)
    _give(db, user.id, 300)
    db.commit()

    resp = _redeem(client, user, reward, quantity=3)

    assert resp.status_code == 201, resp.text
    assert resp.json()["points"] == 150
    assert resp.json()["quantity"] == 3


def test_the_count_is_recorded_not_just_the_points(client: TestClient, db: Session) -> None:
    """Without it the admin sees "150 pts, Cash 500" and has to divide to work
    out whether to hand over one lot or three."""
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    _give(db, user.id, 300)
    db.commit()

    _redeem(client, user, reward, quantity=3)

    req = db.query(RedemptionRequest).filter(RedemptionRequest.user_id == user.id).one()
    assert req.quantity == 3


def test_the_whole_multiplied_amount_is_held(client: TestClient, db: Session) -> None:
    """The hold is the only thing stopping the same balance being spent twice, so
    it has to cover the quantity, not one unit of it."""
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    _give(db, user.id, 300)
    db.commit()

    _redeem(client, user, reward, quantity=4)

    assert ledger.balance(db, user.id) == 300  # nothing debited until approval
    assert ledger.available(db, user.id) == 100


def test_a_quantity_the_balance_cannot_cover_is_refused(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    _give(db, user.id, 120)  # two fit, three do not
    db.commit()

    resp = _redeem(client, user, reward, quantity=3)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "insufficient_balance"
    assert ledger.available(db, user.id) == 120, "a refused request must hold nothing"


def test_an_older_app_build_still_redeems_one(client: TestClient, db: Session) -> None:
    """Builds already on phones send no quantity at all; that has to stay one."""
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    _give(db, user.id, 100)
    db.commit()

    resp = _redeem(client, user, reward)

    assert resp.status_code == 201, resp.text
    assert resp.json()["points"] == 50
    assert resp.json()["quantity"] == 1


def test_a_zero_or_negative_quantity_is_refused(client: TestClient, db: Session) -> None:
    """Zero would otherwise write a points=0 row and trip the CHECK as a 500."""
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    _give(db, user.id, 100)
    db.commit()

    assert _redeem(client, user, reward, quantity=0).status_code == 422
    assert _redeem(client, user, reward, quantity=-5).status_code == 422


def test_an_absurd_quantity_is_refused_rather_than_overflowing(
    client: TestClient, db: Session
) -> None:
    """points is a 32-bit column; cost x quantity must never be asked to exceed
    it, because that surfaces as a 500 instead of a refusal."""
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    _give(db, user.id, 100)
    db.commit()

    assert _redeem(client, user, reward, quantity=10**9).status_code == 422
    assert _redeem(client, user, reward, quantity=redemption.MAX_QUANTITY + 1).status_code == 422


def test_approving_debits_the_multiplied_amount_once(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    admin = make_admin(db)
    _give(db, user.id, 300)
    db.commit()
    req_id = _redeem(client, user, reward, quantity=3).json()["id"]

    resp = client.post(
        f"/api/v1/admin/redemptions/{req_id}/approve",
        headers=admin_headers(admin),
        json={"note": "paid"},
    )

    assert resp.status_code == 200, resp.text
    assert ledger.balance(db, user.id) == 150
    assert ledger.available(db, user.id) == 150


def test_the_admin_list_shows_how_many_to_hand_over(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    admin = make_admin(db)
    _give(db, user.id, 300)
    db.commit()
    _redeem(client, user, reward, quantity=3)

    rows = client.get("/api/v1/admin/redemptions", headers=admin_headers(admin)).json()

    assert rows[0]["quantity"] == 3
    assert rows[0]["reward"]["title"] == reward.title


def test_quantity_cannot_resurrect_an_inactive_reward(client: TestClient, db: Session) -> None:
    user = make_user(db)
    reward = make_reward(db, points_cost=50, is_active=False)
    _give(db, user.id, 300)
    db.commit()

    assert _redeem(client, user, reward, quantity=2).status_code == 409


def test_the_held_price_does_not_move_when_the_reward_is_repriced(
    client: TestClient, db: Session
) -> None:
    """Frozen at create time, quantity included — the same guarantee the single
    redemption already made."""
    user = make_user(db)
    reward = make_reward(db, points_cost=50)
    _give(db, user.id, 300)
    db.commit()
    req_id = _redeem(client, user, reward, quantity=2).json()["id"]

    reward.points_cost = 90
    db.commit()

    req = db.get(RedemptionRequest, uuid.UUID(req_id))
    assert req is not None
    assert req.points == 100
