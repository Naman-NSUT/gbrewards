import threading

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError
from app.models.audit_log import AuditLog
from app.models.ledger_entry import LedgerEntry
from app.models.user import User
from app.services import ledger, redemption
from app.services.ledger import LedgerType
from tests.factories import admin_headers, auth_headers, make_admin, make_user


def _audit_count(db: Session, action: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    ).scalar_one()


def _give(db: Session, user_id, amount: int) -> None:
    ledger.add_entry(db, user_id=user_id, amount=amount, type=LedgerType.ADMIN_CREDIT)


def test_create_holds_against_available(client: TestClient, db: Session) -> None:
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()

    r = client.post("/api/v1/redemptions", headers=auth_headers(user), json={"points": 30})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"

    # pending reduces available; balance unchanged (no ledger row yet)
    assert ledger.balance(db, user.id) == 100
    assert ledger.available(db, user.id) == 70
    assert (
        db.execute(
            select(func.count()).select_from(LedgerEntry).where(LedgerEntry.user_id == user.id)
        ).scalar_one()
        == 1  # only the seed admin_credit
    )


def test_create_exceeding_available_rejected(client: TestClient, db: Session) -> None:
    user = make_user(db)
    _give(db, user.id, 50)
    db.commit()
    r = client.post("/api/v1/redemptions", headers=auth_headers(user), json={"points": 60})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "insufficient_balance"


def test_holds_stack(client: TestClient, db: Session) -> None:
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()
    h = auth_headers(user)
    assert client.post("/api/v1/redemptions", headers=h, json={"points": 60}).status_code == 201
    # 60 held → only 40 available
    assert client.post("/api/v1/redemptions", headers=h, json={"points": 50}).status_code == 400
    assert client.post("/api/v1/redemptions", headers=h, json={"points": 40}).status_code == 201


def test_approve_debits_and_audits(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()

    rid = client.post(
        "/api/v1/redemptions", headers=auth_headers(user), json={"points": 40}
    ).json()["id"]

    r = client.post(
        f"/api/v1/admin/redemptions/{rid}/approve", headers=admin_headers(admin), json={}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assert ledger.balance(db, user.id) == 60  # debited
    assert ledger.available(db, user.id) == 60  # no longer pending
    assert _audit_count(db, "approve_redemption") == 1
    debit = db.execute(
        select(LedgerEntry).where(
            LedgerEntry.user_id == user.id, LedgerEntry.type == "redemption_debit"
        )
    ).scalar_one()
    assert debit.amount == -40
    assert str(debit.redemption_id) == rid


def test_reject_releases_hold(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()

    rid = client.post(
        "/api/v1/redemptions", headers=auth_headers(user), json={"points": 40}
    ).json()["id"]
    r = client.post(
        f"/api/v1/admin/redemptions/{rid}/reject", headers=admin_headers(admin), json={}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert ledger.balance(db, user.id) == 100
    assert ledger.available(db, user.id) == 100  # hold released
    # no redemption_debit row
    assert (
        db.execute(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.type == "redemption_debit")
        ).scalar_one()
        == 0
    )


def test_fulfill_only_from_approved(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()
    h = admin_headers(admin)
    rid = client.post(
        "/api/v1/redemptions", headers=auth_headers(user), json={"points": 20}
    ).json()["id"]

    # cannot fulfill a pending request
    r = client.post(f"/api/v1/admin/redemptions/{rid}/fulfill", headers=h, json={})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_state"

    client.post(f"/api/v1/admin/redemptions/{rid}/approve", headers=h, json={})
    r = client.post(f"/api/v1/admin/redemptions/{rid}/fulfill", headers=h, json={})
    assert r.status_code == 200
    assert r.json()["status"] == "fulfilled"


def test_double_approve_conflicts(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()
    h = admin_headers(admin)
    rid = client.post(
        "/api/v1/redemptions", headers=auth_headers(user), json={"points": 20}
    ).json()["id"]
    first = client.post(f"/api/v1/admin/redemptions/{rid}/approve", headers=h, json={})
    assert first.status_code == 200
    r = client.post(f"/api/v1/admin/redemptions/{rid}/approve", headers=h, json={})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_state"


def test_broker_cancel_pending(client: TestClient, db: Session) -> None:
    user = make_user(db)
    other = make_user(db, phone="+919900008888")
    _give(db, user.id, 100)
    db.commit()
    h = auth_headers(user)
    rid = client.post("/api/v1/redemptions", headers=h, json={"points": 40}).json()["id"]

    # another user cannot cancel it
    other_resp = client.delete(f"/api/v1/redemptions/{rid}", headers=auth_headers(other))
    assert other_resp.status_code == 404

    r = client.delete(f"/api/v1/redemptions/{rid}", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert ledger.available(db, user.id) == 100  # hold released


def test_list_my_redemptions(client: TestClient, db: Session) -> None:
    user = make_user(db)
    _give(db, user.id, 100)
    db.commit()
    h = auth_headers(user)
    client.post("/api/v1/redemptions", headers=h, json={"points": 10})
    client.post("/api/v1/redemptions", headers=h, json={"points": 20})
    r = client.get("/api/v1/redemptions", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_concurrent_creates_cannot_overcommit(db_truncate: sessionmaker) -> None:
    setup = db_truncate()
    user = User(phone="+919900007777", name="Racer")
    setup.add(user)
    setup.flush()
    setup.add(LedgerEntry(user_id=user.id, amount=100, type=str(LedgerType.ADMIN_CREDIT)))
    setup.commit()
    user_id = user.id
    setup.close()

    n = 5
    barrier = threading.Barrier(n)
    results: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        s = db_truncate()
        try:
            u = s.get(User, user_id)
            barrier.wait()
            redemption.create(s, user=u, points=30)
            s.commit()
            with lock:
                results.append("ok")
        except AppError as exc:
            s.rollback()
            with lock:
                results.append(exc.code)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 100 balance / 30 each → at most 3 succeed (90 ≤ 100), and never more.
    accepted = results.count("ok")
    assert accepted <= 3
    assert accepted * 30 <= 100
    assert results.count("insufficient_balance") == n - accepted

    verify = db_truncate()
    held = ledger.pending(verify, user_id)
    assert held <= 100
    assert held == accepted * 30
    verify.close()
