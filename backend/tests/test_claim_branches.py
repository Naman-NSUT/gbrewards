import uuid

import pytest

from app.core.errors import AppError
from app.services import ledger
from app.services.claim import claim
from tests.factories import make_product, make_unit, make_user


def test_unknown_token(db) -> None:  # type: ignore[no-untyped-def]
    user = make_user(db)
    with pytest.raises(AppError) as exc:
        claim(db, user_id=user.id, token=str(uuid.uuid4()))
    assert exc.value.code == "invalid_code"
    assert exc.value.status_code == 404


def test_void_code(db) -> None:  # type: ignore[no-untyped-def]
    user = make_user(db)
    unit = make_unit(db, status="void")
    with pytest.raises(AppError) as exc:
        claim(db, user_id=user.id, token=unit.token)
    assert exc.value.code == "code_void"
    assert exc.value.status_code == 409


def test_already_claimed_by_other(db) -> None:  # type: ignore[no-untyped-def]
    owner = make_user(db, phone="+919900001111")
    other = make_user(db, phone="+919900002222")
    product = make_product(db, points_value=50)
    unit = make_unit(db, product=product)

    claim(db, user_id=owner.id, token=unit.token)
    with pytest.raises(AppError) as exc:
        claim(db, user_id=other.id, token=unit.token)
    assert exc.value.code == "already_claimed"
    assert exc.value.status_code == 409
    assert exc.value.details.get("claimed_at") is not None


def test_happy_path_credits_once(db) -> None:  # type: ignore[no-untyped-def]
    user = make_user(db)
    product = make_product(db, points_value=75)
    unit = make_unit(db, product=product)

    result = claim(db, user_id=user.id, token=unit.token)
    assert result.idempotent is False
    assert result.points_awarded == 75
    assert result.balance == 75
    assert ledger.balance(db, user.id) == 75

    db.refresh(unit)
    assert unit.status == "claimed"
    assert unit.claimed_by_user_id == user.id
