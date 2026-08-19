"""Read units from the dealer programme's own registry."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dealer.models.product import DealerProduct
from app.dealer.models.unit import DealerUnit
from app.dealer.services.unitsource.base import UnitFacts, UnitSource


class LocalUnitSource(UnitSource):
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, serial: str) -> UnitFacts | None:
        row = self.session.execute(
            select(DealerUnit, DealerProduct)
            .join(DealerProduct, DealerProduct.id == DealerUnit.product_id)
            .where(DealerUnit.token == serial)
        ).first()
        if row is None:
            return None
        unit, product = row
        return UnitFacts(
            serial=unit.token,
            product_id=unit.product_id,
            model_name=product.name,
            model_code=product.model_code,
            warranty_months=product.warranty_months,
            # 'active' or 'void'. Whether it has been SOLD is warranties.status.
            source_status=unit.status,
            verified=True,
        )
