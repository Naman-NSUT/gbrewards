"""Returns / reactivation (FR-RT, invariant §3.4).

Reactivating a returned unit flips it claimed -> active and writes a
`return_reversal` ledger entry against the original scanner in the SAME
transaction. The reversed amount is the original credited amount (read from the
ledger), not the product's current points_value.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.ledger_entry import LedgerEntry
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.services import ledger
from app.services.audit import record_audit
from app.services.ledger import LedgerType


@dataclass
class ReactivateResult:
    unit: ProductUnit
    reversed_points: int
    user_id: uuid.UUID


def reactivate_unit(db: Session, *, unit_id: uuid.UUID, admin_id: uuid.UUID) -> ReactivateResult:
    unit = db.execute(
        select(ProductUnit).where(ProductUnit.id == unit_id).with_for_update()
    ).scalar_one_or_none()
    if unit is None:
        raise AppError("invalid_code", 404, "Unknown unit")
    if unit.status != "claimed":
        raise AppError(
            "cannot_reactivate",
            409,
            f"Unit is {unit.status}; only claimed units can be reactivated",
            {"status": unit.status},
        )

    original_user_id = unit.claimed_by_user_id
    assert original_user_id is not None  # guaranteed for a claimed unit

    # Reverse the most recent scan_credit for this unit (the current claim period).
    credit = db.execute(
        select(LedgerEntry)
        .where(
            LedgerEntry.product_unit_id == unit.id,
            LedgerEntry.type == str(LedgerType.SCAN_CREDIT),
        )
        .order_by(LedgerEntry.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if credit is not None:
        reversed_points = credit.amount
    else:
        # Defensive fallback (should not happen): use current product value.
        product = db.get(Product, unit.product_id)
        reversed_points = product.points_value if product is not None else 0

    ledger.add_entry(
        db,
        user_id=original_user_id,
        amount=-reversed_points,
        type=LedgerType.RETURN_REVERSAL,
        product_unit_id=unit.id,
        admin_id=admin_id,
        note="Return reversal",
    )

    unit.status = "active"
    unit.claimed_by_user_id = None
    unit.claimed_at = None

    record_audit(
        db,
        actor_admin_id=admin_id,
        action="reactivate_unit",
        entity_type="product_unit",
        entity_id=unit.id,
        metadata={"reversed_points": reversed_points, "original_user_id": str(original_user_id)},
    )

    return ReactivateResult(unit=unit, reversed_points=reversed_points, user_id=original_user_id)
