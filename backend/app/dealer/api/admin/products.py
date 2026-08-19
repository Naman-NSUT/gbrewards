"""Dealer product catalogue and QR label generation.

The dealer programme owns its serials, so this is where they are created. The
labels printed here are a SECOND QR on the mattress, alongside the factory's —
scanned by the dealer app at point of sale.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_dealer_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, pagination
from app.dealer.models.admin import DealerAdmin
from app.dealer.models.product import DealerProduct
from app.dealer.models.unit import DealerQrBatch, DealerUnit
from app.dealer.schemas.admin import (
    DealerProductIn,
    DealerProductOut,
    GenerateBatchIn,
    Paginated,
    QrBatchOut,
)
from app.dealer.services import qr
from app.dealer.services.audit import record_audit

router = APIRouter(tags=["dealer-admin-products"])


def _product_out(db: Session, product: DealerProduct) -> DealerProductOut:
    units = int(
        db.execute(
            select(func.count())
            .select_from(DealerUnit)
            .where(DealerUnit.product_id == product.id)
        ).scalar_one()
    )
    return DealerProductOut(
        id=product.id,
        name=product.name,
        description=product.description,
        terms=product.terms,
        model_code=product.model_code,
        warranty_months=product.warranty_months,
        is_active=product.is_active,
        units_generated=units,
    )


@router.get("/products", response_model=Paginated[DealerProductOut])
def list_products(
    q: str | None = Query(default=None, max_length=200),
    is_active: bool | None = None,
    page: Pagination = Depends(pagination),
    _: DealerAdmin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[DealerProductOut]:
    stmt = select(DealerProduct)
    if q:
        stmt = stmt.where(DealerProduct.name.ilike(f"%{q}%"))
    if is_active is not None:
        stmt = stmt.where(DealerProduct.is_active.is_(is_active))
    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rows = db.execute(
        stmt.order_by(DealerProduct.name).limit(page.limit).offset(page.offset)
    ).scalars()
    return Paginated[DealerProductOut](
        items=[_product_out(db, p) for p in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/products", response_model=DealerProductOut, status_code=201)
def create_product(
    body: DealerProductIn,
    request: Request,
    admin: DealerAdmin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> DealerProductOut:
    product = DealerProduct(**body.model_dump())
    db.add(product)
    db.flush()
    record_audit(
        db,
        action="create_product",
        entity_type="dealer_product",
        entity_id=product.id,
        actor_id=admin.id,
        metadata={"name": product.name, "warranty_months": product.warranty_months},
        ip=client_ip(request),
    )
    db.commit()
    return _product_out(db, product)


@router.patch("/products/{product_id}", response_model=DealerProductOut)
def update_product(
    product_id: uuid.UUID,
    body: DealerProductIn,
    request: Request,
    admin: DealerAdmin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> DealerProductOut:
    product = db.get(DealerProduct, product_id)
    if product is None:
        raise AppError("product_not_found", 404, "Unknown product")

    before = {"name": product.name, "warranty_months": product.warranty_months}
    for field, value in body.model_dump().items():
        setattr(product, field, value)
    db.flush()
    record_audit(
        db,
        action="update_product",
        entity_type="dealer_product",
        entity_id=product.id,
        actor_id=admin.id,
        # Changing warranty_months does NOT touch warranties already sold — the
        # length is frozen onto each warranty at registration.
        metadata={"before": before, "after": {"name": product.name,
                                              "warranty_months": product.warranty_months}},
        ip=client_ip(request),
    )
    db.commit()
    return _product_out(db, product)


@router.post("/products/{product_id}/batches", response_model=QrBatchOut, status_code=201)
def generate_batch(
    product_id: uuid.UUID,
    body: GenerateBatchIn,
    request: Request,
    admin: DealerAdmin = Depends(require_admin_write),
    db: Session = Depends(get_db),
) -> QrBatchOut:
    """Mint `quantity` new dealer serials and their printable labels."""
    batch = qr.generate_batch(
        db,
        product_id=product_id,
        quantity=body.quantity,
        label=body.label,
        admin_id=admin.id,
    )
    record_audit(
        db,
        action="generate_qr_batch",
        entity_type="dealer_qr_batch",
        entity_id=batch.id,
        actor_id=admin.id,
        metadata={"product_id": str(product_id), "quantity": body.quantity},
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(batch)
    return QrBatchOut.model_validate(batch)


@router.get("/batches", response_model=Paginated[QrBatchOut])
def list_batches(
    product_id: uuid.UUID | None = None,
    page: Pagination = Depends(pagination),
    _: DealerAdmin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[QrBatchOut]:
    stmt = select(DealerQrBatch)
    if product_id is not None:
        stmt = stmt.where(DealerQrBatch.product_id == product_id)
    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rows = db.execute(
        stmt.order_by(DealerQrBatch.created_at.desc()).limit(page.limit).offset(page.offset)
    ).scalars()
    return Paginated[QrBatchOut](
        items=[QrBatchOut.model_validate(b) for b in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/batches/{batch_id}/labels.pdf")
def export_labels(
    batch_id: uuid.UUID,
    _: DealerAdmin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Response:
    """The printable sheet — one label per unit, one per page."""
    pdf = qr.render_batch_pdf(db, batch_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="dealer-labels-{batch_id}.pdf"'},
    )
