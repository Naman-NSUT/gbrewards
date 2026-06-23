from sqlalchemy import func, select

from app.models.ledger_entry import LedgerEntry
from app.services import ledger
from app.services.claim import claim
from tests.factories import make_product, make_unit, make_user


def test_same_user_rescan_is_idempotent(db) -> None:  # type: ignore[no-untyped-def]
    user = make_user(db)
    product = make_product(db, points_value=120)
    unit = make_unit(db, product=product)

    first = claim(db, user_id=user.id, token=unit.token)
    assert first.idempotent is False
    assert first.points_awarded == 120

    second = claim(db, user_id=user.id, token=unit.token)
    assert second.idempotent is True
    assert second.points_awarded == 120
    assert second.balance == 120

    # No double credit: exactly one scan_credit ledger row, balance == P (not 2P).
    count = db.execute(
        select(func.count()).select_from(LedgerEntry).where(LedgerEntry.product_unit_id == unit.id)
    ).scalar_one()
    assert count == 1
    assert ledger.balance(db, user.id) == 120
