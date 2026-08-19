"""Builders for dealer-side tests.

A "unit" is no longer a mirrored copy — it is a real `product_units` row created
the way manufacturing creates one, under a real `products` row. That means these
tests exercise the same join the production code does, rather than a stand-in
that could drift from it.
"""

import uuid

from sqlalchemy.orm import Session

from app.dealer.models.allocation import Allocation
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.point_rate import PointRate
from app.models.admin import Admin
from app.models.product import Product
from app.models.product_unit import ProductUnit


def make_admin(db: Session, email: str = "admin@example.com", role: str = "owner") -> Admin:
    admin = Admin(email=email, password_hash="x", name="Admin", role=role)
    db.add(admin)
    db.flush()
    return admin


def make_dealer(db: Session, code: str = "D001", name: str = "Shop One") -> Dealer:
    dealer = Dealer(code=code, name=name)
    db.add(dealer)
    db.flush()
    return dealer


def make_staff(db: Session, dealer: Dealer, phone: str = "+919000000001") -> DealerStaff:
    staff = DealerStaff(dealer_id=dealer.id, phone=phone, name="Seller", role="owner")
    db.add(staff)
    db.flush()
    return staff


def make_product(db: Session, name: str = "GoodBed HR Foam", months: int = 60) -> Product:
    product = Product(
        name=name,
        description="Test product",
        points_value=10,          # what a factory worker earns for assembling it
        warranty_months=months,   # dealer-side warranty length
        is_active=True,
    )
    db.add(product)
    db.flush()
    return product


def make_rate(db: Session, points: int = 50, product: Product | None = None) -> PointRate:
    """Set the dealer registration rate FOR A PRODUCT.

    Goes through the real rate-change path so the "only one current rate per
    product" index is exercised rather than side-stepped.
    """
    from app.dealer.services.ledger import set_rate

    if product is None:
        product = make_product(db, name=f"Auto {uuid.uuid4().hex[:6]}")
    return set_rate(db, product_id=product.id, points_per_registration=points)


def make_unit(
    db: Session, serial: str, months: int = 60, product: Product | None = None
) -> ProductUnit:
    """A real manufactured unit. `serial` is the QR token printed on the label."""
    if product is None:
        product = make_product(db, name=f"Model {uuid.uuid4().hex[:6]}", months=months)
    unit = ProductUnit(product_id=product.id, token=serial, status="active")
    db.add(unit)
    db.flush()
    return unit


def make_priced_unit(
    db: Session, serial: str, points: int = 50, months: int = 60
) -> tuple[ProductUnit, Product]:
    """A unit whose product has a dealer registration rate set — the usual case."""
    product = make_product(db, name=f"Model {uuid.uuid4().hex[:6]}", months=months)
    unit = make_unit(db, serial, product=product)
    make_rate(db, points, product=product)
    return unit, product


def allocate(db: Session, serial: str, dealer: Dealer) -> Allocation:
    allocation = Allocation(serial=serial, dealer_id=dealer.id, status="allocated")
    db.add(allocation)
    db.flush()
    return allocation


def new_serial() -> str:
    return str(uuid.uuid4())
