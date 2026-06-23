"""The atomic scan-claim (TECH_SPEC §5). A code is claimed at most once per
active period; points are credited exactly once, in the same transaction as the
status flip.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.services import ledger
from app.services.ledger import LedgerType


@dataclass
class ClaimResult:
    product: Product
    points_awarded: int
    balance: int
    available: int
    idempotent: bool
    claimed_at: datetime


def _load_unit(session: Session, token: str) -> ProductUnit:
    unit = session.execute(
        select(ProductUnit).where(ProductUnit.token == token)
    ).scalar_one_or_none()
    if unit is None:
        raise AppError("invalid_code", 404, "Unknown or invalid code")
    return unit


def claim(session: Session, *, user_id: uuid.UUID, token: str) -> ClaimResult:
    unit = _load_unit(session, token)
    product = session.get(Product, unit.product_id)
    assert product is not None  # FK guarantees existence

    result = _resolve(session, unit, product, user_id, attempt_active=True)
    session.commit()
    return result


def _resolve(
    session: Session,
    unit: ProductUnit,
    product: Product,
    user_id: uuid.UUID,
    *,
    attempt_active: bool,
) -> ClaimResult:
    if unit.status == "void":
        raise AppError("code_void", 409, "This code has been voided")

    if unit.status == "claimed":
        if unit.claimed_by_user_id == user_id:
            return _idempotent_result(session, unit, product, user_id)
        raise AppError(
            "already_claimed",
            409,
            "This code has already been claimed",
            {"claimed_at": unit.claimed_at.isoformat() if unit.claimed_at else None},
        )

    # status == 'active' — atomic conditional claim.
    won = session.execute(
        update(ProductUnit)
        .where(ProductUnit.id == unit.id, ProductUnit.status == "active")
        .values(status="claimed", claimed_by_user_id=user_id, claimed_at=func.now())
        .returning(ProductUnit.id)
    ).first()

    if won is None:
        # Lost the race — re-read the now-committed-by-winner row and branch.
        session.expire(unit)
        fresh = session.get(ProductUnit, unit.id)
        assert fresh is not None
        return _resolve(session, fresh, product, user_id, attempt_active=False)

    ledger.add_entry(
        session,
        user_id=user_id,
        amount=product.points_value,
        type=LedgerType.SCAN_CREDIT,
        product_unit_id=unit.id,
    )
    session.flush()
    session.refresh(unit)
    return ClaimResult(
        product=product,
        points_awarded=product.points_value,
        balance=ledger.balance(session, user_id),
        available=ledger.available(session, user_id),
        idempotent=False,
        claimed_at=unit.claimed_at,  # type: ignore[arg-type]
    )


def _idempotent_result(
    session: Session, unit: ProductUnit, product: Product, user_id: uuid.UUID
) -> ClaimResult:
    from app.models.ledger_entry import LedgerEntry

    entry = session.execute(
        select(LedgerEntry).where(
            LedgerEntry.product_unit_id == unit.id,
            LedgerEntry.type == str(LedgerType.SCAN_CREDIT),
            LedgerEntry.user_id == user_id,
        )
    ).scalar_one_or_none()
    points = entry.amount if entry is not None else product.points_value
    return ClaimResult(
        product=product,
        points_awarded=points,
        balance=ledger.balance(session, user_id),
        available=ledger.available(session, user_id),
        idempotent=True,
        claimed_at=unit.claimed_at,  # type: ignore[arg-type]
    )
