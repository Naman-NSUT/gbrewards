"""Read units straight out of the shared database."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dealer.services.unitsource.base import UnitFacts, UnitSource
from app.models.product import Product
from app.models.product_unit import ProductUnit


class LocalUnitSource(UnitSource):
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, serial: str) -> UnitFacts | None:
        row = self.session.execute(
            select(ProductUnit, Product)
            .join(Product, Product.id == ProductUnit.product_id)
            .where(ProductUnit.token == serial)
        ).first()
        if row is None:
            return None
        unit, product = row
        return UnitFacts(
            serial=unit.token,
            product_id=unit.product_id,
            model_name=product.name,
            model_code=None,
            # Per-product warranty length, set in the dealer admin panel.
            # Falls back to the configured default so a product nobody has
            # configured yet still registers rather than blocking a sale.
            warranty_months=product.warranty_months or settings.default_warranty_months,
            source_status=unit.status,
            verified=True,
        )
