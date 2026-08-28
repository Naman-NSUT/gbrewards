"""Dealer product catalogue.

A product is what a shop picks from the dropdown when it registers a sale, so
this list decides two things that cost money: the warranty length frozen onto
each warranty, and — through the product's point rate — what registering it
pays. Deactivating a product is how the client takes a discontinued model off
that dropdown.

Nothing here mints serials any more. The dealer app no longer scans, so the
batch-minting and label-sheet endpoints that fed the scanner are gone. The
`dealer_qr_batches` and `dealer_units` rows stay and GET /batches still reads
them: they are the record of what was physically printed, and warranties
registered before the change still carry those serials.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import client_ip, get_current_dealer_admin, get_db, require_admin_write
from app.core.errors import AppError
from app.dealer.api.admin._common import Pagination, pagination
from app.dealer.models.admin import DealerAdmin
from app.dealer.models.product import DealerProduct
from app.dealer.models.unit import DealerQrBatch
from app.dealer.schemas.admin import DealerProductIn, DealerProductOut, Paginated, QrBatchOut
from app.dealer.services.audit import record_audit

router = APIRouter(tags=["dealer-admin-products"])


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
        items=[DealerProductOut.model_validate(p) for p in rows],
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
    return DealerProductOut.model_validate(product)


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
        metadata={
            "before": before,
            "after": {"name": product.name, "warranty_months": product.warranty_months},
        },
        ip=client_ip(request),
    )
    db.commit()
    return DealerProductOut.model_validate(product)


@router.get("/batches", response_model=Paginated[QrBatchOut])
def list_batches(
    product_id: uuid.UUID | None = None,
    page: Pagination = Depends(pagination),
    _: DealerAdmin = Depends(get_current_dealer_admin),
    db: Session = Depends(get_db),
) -> Paginated[QrBatchOut]:
    """Batches that were printed before the scanner was retired. Read only.

    Nothing can mint a new one, so this never grows. It stays because support
    still gets calls about a label somebody is holding, and the batch is how you
    find out when it was printed and for which product.
    """
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
