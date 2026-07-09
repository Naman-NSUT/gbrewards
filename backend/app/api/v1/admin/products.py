import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.core.errors import AppError
from app.models.admin import Admin
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.models.qr_batch import QrBatch
from app.schemas.admin import (
    BatchCreateIn,
    BatchOut,
    OrderBatchLine,
    OrderCreateIn,
    OrderCreateOut,
    ProductIn,
    ProductOut,
    ProductUpdateIn,
    ProductWithCounts,
)
from app.services.audit import record_audit
from app.services.products import product_counts
from app.services.qr import generate_batch, generate_order, render_batch_pdf, render_order_pdf

router = APIRouter(tags=["admin-products"])


def _get_product_or_404(db: Session, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise AppError("invalid_code", 404, "Unknown product")
    return product


@router.get("/products", response_model=list[ProductOut])
def list_products(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[Product]:
    return list(db.execute(select(Product).order_by(Product.created_at.desc())).scalars())


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(
    body: ProductIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Product:
    product = Product(
        name=body.name,
        description=body.description,
        terms=body.terms,
        points_value=body.points_value,
        is_active=body.is_active,
    )
    db.add(product)
    db.flush()
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="create_product",
        entity_type="product",
        entity_id=product.id,
        metadata={"name": product.name, "points_value": product.points_value},
    )
    db.commit()
    db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductWithCounts)
def get_product(
    product_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> ProductWithCounts:
    product = _get_product_or_404(db, product_id)
    counts = product_counts(db, product_id)
    return ProductWithCounts(
        id=product.id,
        name=product.name,
        description=product.description,
        points_value=product.points_value,
        is_active=product.is_active,
        created_at=product.created_at,
        units_generated=counts["units_generated"],
        units_claimed=counts["units_claimed"],
        units_available=counts["units_available"],
        units_void=counts["units_void"],
    )


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID,
    body: ProductUpdateIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Product:
    product = _get_product_or_404(db, product_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(product, field, value)
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="update_product",
        entity_type="product",
        entity_id=product.id,
        metadata={"changes": changes},
    )
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    product = _get_product_or_404(db, product_id)
    unit_count = db.execute(
        select(func.count()).select_from(ProductUnit).where(ProductUnit.product_id == product_id)
    ).scalar_one()
    if unit_count:
        raise AppError(
            "product_in_use",
            409,
            "This product has generated QR codes and can't be deleted; deactivate it instead.",
            {"units": int(unit_count)},
        )
    db.execute(delete(QrBatch).where(QrBatch.product_id == product_id))
    record_audit(
        db,
        actor_admin_id=admin.id,
        action="delete_product",
        entity_type="product",
        entity_id=product.id,
        metadata={"name": product.name},
    )
    db.delete(product)
    db.commit()


@router.post("/products/{product_id}/batches", response_model=BatchOut, status_code=201)
def create_batch(
    product_id: uuid.UUID,
    body: BatchCreateIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> QrBatch:
    _get_product_or_404(db, product_id)
    batch = generate_batch(
        db,
        product_id=product_id,
        quantity=body.quantity,
        label=body.label,
        admin_id=admin.id,
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches/{batch_id}/export")
def export_batch(
    batch_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    format: str = Query(default="pdf"),
) -> StreamingResponse:
    if format != "pdf":
        raise AppError("unsupported_format", 400, "Only pdf export is supported")
    pdf_bytes = render_batch_pdf(db, batch_id)
    headers = {"Content-Disposition": f'attachment; filename="batch-{batch_id}.pdf"'}
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers=headers)


@router.post("/orders", response_model=OrderCreateOut, status_code=201)
def create_order(
    body: OrderCreateIn,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> OrderCreateOut:
    """Generate QR codes for a multi-product order — one batch per line item."""
    batches = generate_order(
        db,
        items=[(i.product_id, i.quantity) for i in body.items],
        label=body.label,
        admin_id=admin.id,
    )
    db.commit()

    lines: list[OrderBatchLine] = []
    total = 0
    for batch in batches:
        db.refresh(batch)
        product = db.get(Product, batch.product_id)
        assert product is not None
        lines.append(
            OrderBatchLine(
                batch_id=batch.id,
                product_id=batch.product_id,
                product_name=product.name,
                quantity=batch.quantity,
            )
        )
        total += batch.quantity
    return OrderCreateOut(label=body.label, total_units=total, batches=lines)


@router.get("/orders/export")
def export_order(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    ids: list[uuid.UUID] = Query(default_factory=list),
    format: str = Query(default="pdf"),
) -> StreamingResponse:
    if format != "pdf":
        raise AppError("unsupported_format", 400, "Only pdf export is supported")
    if not ids:
        raise AppError("validation_error", 400, "At least one batch id is required")
    pdf_bytes = render_order_pdf(db, ids)
    headers = {"Content-Disposition": 'attachment; filename="qr-order.pdf"'}
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers=headers)
