import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.core.errors import AppError
from app.models.admin import Admin
from app.models.ledger_entry import LedgerEntry
from app.models.product_unit import ProductUnit
from app.schemas.admin import ReactivateOut, UnitDetailOut, UnitOut
from app.schemas.ledger import LedgerEntryOut
from app.services.audit import record_audit
from app.services.returns import reactivate_unit

router = APIRouter(tags=["admin-units"])


@router.get("/units", response_model=list[UnitOut])
def list_units(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    product_id: uuid.UUID | None = None,
    status: str | None = None,
    q: str | None = Query(default=None, description="token substring / exact token"),
) -> list[ProductUnit]:
    stmt = select(ProductUnit)
    if product_id is not None:
        stmt = stmt.where(ProductUnit.product_id == product_id)
    if status is not None:
        stmt = stmt.where(ProductUnit.status == status)
    if q:
        stmt = stmt.where(ProductUnit.token.ilike(f"%{q}%"))
    stmt = stmt.order_by(ProductUnit.created_at.desc()).limit(200)
    return list(db.execute(stmt).scalars())


@router.get("/units/{token}", response_model=UnitDetailOut)
def get_unit(
    token: str,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UnitDetailOut:
    unit = db.execute(select(ProductUnit).where(ProductUnit.token == token)).scalar_one_or_none()
    if unit is None:
        raise AppError("invalid_code", 404, "Unknown unit")

    history = list(
        db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.product_unit_id == unit.id)
            .order_by(LedgerEntry.created_at.desc())
        ).scalars()
    )
    return UnitDetailOut(
        **UnitOut.model_validate(unit).model_dump(),
        history=[LedgerEntryOut.model_validate(h) for h in history],
    )


@router.post("/units/{unit_id}/void", response_model=UnitOut)
def void_unit(
    unit_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ProductUnit:
    unit = db.get(ProductUnit, unit_id)
    if unit is None:
        raise AppError("invalid_code", 404, "Unknown unit")
    if unit.status == "claimed":
        raise AppError("cannot_void_claimed", 409, "Cannot void a claimed unit; reactivate first")
    if unit.status == "void":
        return unit

    unit.status = "void"
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="void_unit",
        entity_type="product_unit",
        entity_id=unit.id,
        metadata={"token": unit.token},
    )
    db.commit()
    db.refresh(unit)
    return unit


@router.post("/units/{unit_id}/reactivate", response_model=ReactivateOut)
def reactivate(
    unit_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ReactivateOut:
    result = reactivate_unit(db, unit_id=unit_id, admin_id=admin.id)
    db.commit()
    db.refresh(result.unit)
    return ReactivateOut(
        unit=UnitOut.model_validate(result.unit),
        reversed_points=result.reversed_points,
        user_id=result.user_id,
    )
