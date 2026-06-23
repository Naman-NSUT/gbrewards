from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.ledger_entry import LedgerEntry
from app.services import ledger
from app.services.claim import claim
from app.services.ledger import LedgerType
from tests.factories import admin_headers, make_admin, make_product, make_unit, make_user


def _audit_count(db: Session, action: str) -> int:
    return db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    ).scalar_one()


def test_reactivate_reverses_credit(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    product = make_product(db, points_value=100)
    unit = make_unit(db, product=product)
    db.flush()
    claim(db, user_id=user.id, token=unit.token)
    db.commit()
    assert ledger.balance(db, user.id) == 100

    r = client.post(f"/api/v1/admin/units/{unit.id}/reactivate", headers=admin_headers(admin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reversed_points"] == 100
    assert body["user_id"] == str(user.id)
    assert body["unit"]["status"] == "active"
    assert body["unit"]["claimed_by_user_id"] is None

    db.expire_all()
    assert ledger.balance(db, user.id) == 0
    assert _audit_count(db, "reactivate_unit") == 1
    reversal = db.execute(
        select(LedgerEntry).where(
            LedgerEntry.product_unit_id == unit.id,
            LedgerEntry.type == "return_reversal",
        )
    ).scalar_one()
    assert reversal.amount == -100
    assert reversal.user_id == user.id


def test_cannot_reactivate_active_or_void(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    active = make_unit(db, status="active")
    void = make_unit(db, status="void")
    db.commit()
    h = admin_headers(admin)

    r = client.post(f"/api/v1/admin/units/{active.id}/reactivate", headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "cannot_reactivate"

    r = client.post(f"/api/v1/admin/units/{void.id}/reactivate", headers=h)
    assert r.status_code == 409


def test_double_reactivate_conflicts(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    unit = make_unit(db, product=make_product(db, points_value=50))
    db.flush()
    claim(db, user_id=user.id, token=unit.token)
    db.commit()
    h = admin_headers(admin)

    assert client.post(f"/api/v1/admin/units/{unit.id}/reactivate", headers=h).status_code == 200
    r = client.post(f"/api/v1/admin/units/{unit.id}/reactivate", headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "cannot_reactivate"


def test_reclaim_after_reactivation_reverses_second_user(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user_a = make_user(db, phone="+919900001111")
    user_b = make_user(db, phone="+919900002222")
    product = make_product(db, points_value=70)
    unit = make_unit(db, product=product)
    db.flush()
    h = admin_headers(admin)

    # A claims, returned, reactivated -> A reversed to 0
    claim(db, user_id=user_a.id, token=unit.token)
    db.commit()
    client.post(f"/api/v1/admin/units/{unit.id}/reactivate", headers=h)
    db.expire_all()
    assert ledger.balance(db, user_a.id) == 0

    # B claims the reactivated unit
    db.refresh(unit)
    claim(db, user_id=user_b.id, token=unit.token)
    db.commit()
    assert ledger.balance(db, user_b.id) == 70

    # reactivate again -> reverses B, not A
    r = client.post(f"/api/v1/admin/units/{unit.id}/reactivate", headers=h)
    assert r.json()["user_id"] == str(user_b.id)
    db.expire_all()
    assert ledger.balance(db, user_b.id) == 0
    assert ledger.balance(db, user_a.id) == 0


def test_reversal_uses_original_amount_not_current_price(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    product = make_product(db, points_value=100)
    unit = make_unit(db, product=product)
    db.flush()
    claim(db, user_id=user.id, token=unit.token)
    # product value changes AFTER the scan
    product.points_value = 999
    db.commit()

    r = client.post(f"/api/v1/admin/units/{unit.id}/reactivate", headers=admin_headers(admin))
    assert r.json()["reversed_points"] == 100  # original credit, not 999
    db.expire_all()
    assert ledger.balance(db, user.id) == 0


def test_reversal_allows_negative_balance(client: TestClient, db: Session) -> None:
    admin = make_admin(db)
    user = make_user(db)
    product = make_product(db, points_value=100)
    unit = make_unit(db, product=product)
    db.flush()
    claim(db, user_id=user.id, token=unit.token)
    # user spends the points (admin debit), then the unit is returned
    ledger.add_entry(db, user_id=user.id, amount=-100, type=LedgerType.ADMIN_DEBIT)
    db.commit()
    assert ledger.balance(db, user.id) == 0

    client.post(f"/api/v1/admin/units/{unit.id}/reactivate", headers=admin_headers(admin))
    db.expire_all()
    assert ledger.balance(db, user.id) == -100  # D3: negative allowed
