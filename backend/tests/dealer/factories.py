"""Builders for dealer-programme tests.

Everything here is dealer-owned. A "unit" is a `dealer_units` row minted the way
the dealer admin mints one — through the real QR batch service — under a
`dealer_products` row. Nothing touches the worker programme's tables.
"""

import uuid

from sqlalchemy.orm import Session

from app.dealer.models.admin import DealerAdmin
from app.dealer.models.allocation import Allocation
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.point_rate import PointRate
from app.dealer.models.product import DealerProduct
from app.dealer.models.unit import DealerUnit


def make_admin(db: Session, email: str = "admin@example.com", role: str = "owner") -> DealerAdmin:
    admin = DealerAdmin(email=email, password_hash="x", name="Admin", role=role)
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


def make_product(db: Session, name: str = "GoodBed HR Foam", months: int = 60) -> DealerProduct:
    product = DealerProduct(
        name=name,
        description="Test product",
        warranty_months=months,
        is_active=True,
    )
    db.add(product)
    db.flush()
    return product


def make_rate(db: Session, points: int = 50, product: DealerProduct | None = None) -> PointRate:
    """Set the registration rate FOR A PRODUCT, via the real rate-change path so
    the one-current-rate-per-product index is exercised rather than side-stepped."""
    from app.dealer.services.ledger import set_rate

    if product is None:
        product = make_product(db, name=f"Auto {uuid.uuid4().hex[:6]}")
    return set_rate(db, product_id=product.id, points_per_registration=points)


def make_unit(
    db: Session, serial: str, months: int = 60, product: DealerProduct | None = None
) -> DealerUnit:
    """A dealer serial. `serial` is the token printed on the DEALER label — not
    the factory's; the two are unrelated."""
    if product is None:
        product = make_product(db, name=f"Model {uuid.uuid4().hex[:6]}", months=months)
    unit = DealerUnit(product_id=product.id, token=serial, status="active")
    db.add(unit)
    db.flush()
    return unit


def make_priced_unit(
    db: Session, serial: str, points: int = 50, months: int = 60
) -> tuple[DealerUnit, DealerProduct]:
    """A unit whose product has a registration rate — the usual case."""
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
