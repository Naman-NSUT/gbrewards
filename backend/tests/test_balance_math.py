from sqlalchemy.orm import Session

from app.models.redemption_request import RedemptionRequest
from app.services import ledger
from app.services.ledger import LedgerType
from tests.factories import make_user


def test_empty_balance_is_zero(db: Session) -> None:
    user = make_user(db)
    assert ledger.balance(db, user.id) == 0
    assert ledger.available(db, user.id) == 0


def test_credit_and_debit_sum(db: Session) -> None:
    user = make_user(db)
    ledger.add_entry(db, user_id=user.id, amount=100, type=LedgerType.SCAN_CREDIT)
    ledger.add_entry(db, user_id=user.id, amount=-30, type=LedgerType.ADMIN_DEBIT)
    assert ledger.balance(db, user.id) == 70


def test_pending_reduces_available(db: Session) -> None:
    user = make_user(db)
    ledger.add_entry(db, user_id=user.id, amount=100, type=LedgerType.SCAN_CREDIT)
    db.add(RedemptionRequest(user_id=user.id, points=20, status="pending"))
    db.flush()
    assert ledger.balance(db, user.id) == 100
    assert ledger.pending(db, user.id) == 20
    assert ledger.available(db, user.id) == 80


def test_multiple_pendings_sum_and_non_pending_excluded(db: Session) -> None:
    user = make_user(db)
    ledger.add_entry(db, user_id=user.id, amount=100, type=LedgerType.SCAN_CREDIT)
    db.add_all(
        [
            RedemptionRequest(user_id=user.id, points=10, status="pending"),
            RedemptionRequest(user_id=user.id, points=15, status="pending"),
            RedemptionRequest(user_id=user.id, points=50, status="approved"),
            RedemptionRequest(user_id=user.id, points=5, status="rejected"),
        ]
    )
    db.flush()
    assert ledger.pending(db, user.id) == 25
    assert ledger.available(db, user.id) == 75


def test_negative_balance_allowed(db: Session) -> None:
    # D3: reversal/debit may push balance negative; allowed, flagged to admin.
    user = make_user(db)
    ledger.add_entry(db, user_id=user.id, amount=50, type=LedgerType.SCAN_CREDIT)
    ledger.add_entry(db, user_id=user.id, amount=-80, type=LedgerType.RETURN_REVERSAL)
    assert ledger.balance(db, user.id) == -30
