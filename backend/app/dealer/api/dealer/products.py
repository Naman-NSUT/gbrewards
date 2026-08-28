"""The catalogue a shop picks from when registering a sale.

Registration used to identify the mattress by scanning its label, so the app
never needed to know what products existed — the serial answered that. Now the
dealer chooses the product, which means the app needs a list, and there was no
endpoint a `dealer` token could read: /dealer-admin/products is the back office
(aud='dealer_admin') and /products is the worker programme's own catalogue.

Deliberately lean. A shop assistant picking from a dropdown at a counter needs
the name, the model code printed on the box, and the cover length so they can
tell a 36-month model from a 60-month one. Terms are label copy, is_active is a
back-office concern, and neither belongs on a phone.

Inactive products are absent rather than disabled: a product that should not be
sold should not be offerable, and filtering here means the app cannot get it
wrong.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_staff, get_db
from app.dealer.models.dealer import DealerStaff
from app.dealer.models.product import DealerProduct
from app.dealer.schemas.common import Base

router = APIRouter(tags=["dealer-products"])


class DealerCatalogueItem(Base):
    id: str
    name: str
    model_code: str | None
    warranty_months: int


@router.get("/products", response_model=list[DealerCatalogueItem])
def list_products(
    _staff: DealerStaff = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> list[DealerCatalogueItem]:
    """Active products, by name — the order a human scans a dropdown in."""
    rows = (
        db.execute(
            select(DealerProduct)
            .where(DealerProduct.is_active.is_(True))
            .order_by(DealerProduct.name)
        )
        .scalars()
        .all()
    )
    return [
        DealerCatalogueItem(
            id=str(p.id),
            name=p.name,
            model_code=p.model_code,
            warranty_months=p.warranty_months,
        )
        for p in rows
    ]
