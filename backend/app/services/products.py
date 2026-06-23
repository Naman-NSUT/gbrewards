import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product_unit import ProductUnit


def product_counts(session: Session, product_id: uuid.UUID) -> dict[str, int]:
    """Unit counts by status for a product (FR-D4)."""
    rows = session.execute(
        select(ProductUnit.status, func.count())
        .where(ProductUnit.product_id == product_id)
        .group_by(ProductUnit.status)
    ).all()
    by_status = {status: count for status, count in rows}
    claimed = by_status.get("claimed", 0)
    active = by_status.get("active", 0)
    void = by_status.get("void", 0)
    return {
        "units_generated": claimed + active + void,
        "units_claimed": claimed,
        "units_available": active,
        "units_void": void,
    }
