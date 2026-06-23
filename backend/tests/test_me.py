from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import ledger
from app.services.ledger import LedgerType
from tests.factories import auth_headers, make_user


def test_get_me(client: TestClient, db: Session) -> None:
    user = make_user(db, name="Mia")
    ledger.add_entry(db, user_id=user.id, amount=80, type=LedgerType.ADMIN_CREDIT)
    db.commit()

    r = client.get("/api/v1/me", headers=auth_headers(user))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Mia"
    assert body["balance"] == 80
    assert body["available"] == 80


def test_patch_me_updates_name(client: TestClient, db: Session) -> None:
    user = make_user(db, name="Old")
    db.commit()
    r = client.patch("/api/v1/me", headers=auth_headers(user), json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"
    db.expire_all()
    assert db.get(type(user), user.id).name == "New Name"


def test_get_me_sets_last_active(client: TestClient, db: Session) -> None:
    user = make_user(db)
    db.commit()
    assert user.last_active_at is None
    client.get("/api/v1/me", headers=auth_headers(user))
    db.expire_all()
    refreshed = db.get(type(user), user.id)
    assert refreshed is not None
    assert refreshed.last_active_at is not None


def test_me_ledger_pagination(client: TestClient, db: Session) -> None:
    user = make_user(db)
    for i in range(5):
        ledger.add_entry(db, user_id=user.id, amount=i + 1, type=LedgerType.ADMIN_CREDIT)
    db.commit()
    h = auth_headers(user)

    # page through with limit=2 and assert every entry is seen exactly once
    seen: list[int] = []
    cursor: str | None = None
    pages = 0
    while True:
        url = "/api/v1/me/ledger?limit=2" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url, headers=h).json()
        seen.extend(item["amount"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
        assert pages < 10  # guard against a pagination loop
    assert sorted(seen) == [1, 2, 3, 4, 5]


def test_me_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"
