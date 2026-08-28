"""Builders for dealer-programme tests.

Everything here is dealer-owned; nothing touches the worker programme's tables.

The split in this file mirrors the split in the product. A dealer registering a
sale today picks a PRODUCT and types an invoice number — `make_priced_product`
and `new_invoice` build that world. A `dealer_units` row is a serial that was
printed on a label before the scanner was retired; `make_unit` still builds
those because the paths a customer reaches a warranty BY — public lookup by
serial, claims, the admin serial screen — are still serial-addressed, and
`make_legacy_warranty` builds the pre-0011 warranty rows they answer about.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.dealer.models.admin import DealerAdmin
from app.dealer.models.customer import Customer
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.point_rate import PointRate
from app.dealer.models.product import DealerProduct
from app.dealer.models.unit import DealerUnit
from app.dealer.models.warranty import Warranty, WarrantyEvent
from app.dealer.services.warranty_dates import add_months, business_today


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


def make_priced_product(
    db: Session, points: int = 50, months: int = 60, name: str | None = None
) -> DealerProduct:
    """What a dealer picks from the dropdown: a product that is worth something.

    The product now carries everything a registration used to read off a label —
    the model name, the warranty length, and through its rate the points — so
    this one row is the whole "what was sold" side of a sale. A product with no
    rate registers perfectly well and earns nothing, which is a test of its own
    rather than something a fixture should leave to chance.
    """
    product = make_product(db, name=name or f"Model {uuid.uuid4().hex[:6]}", months=months)
    make_rate(db, points, product=product)
    return product


def new_invoice(prefix: str = "INV") -> str:
    """A fresh invoice number.

    One live warranty per (dealer, invoice) is the whole cap on farming now, so
    a test that registers two sales for one shop needs two of these. Reusing one
    does not register twice — it earns the 409 that protects real money, which
    is a confusing way for an unrelated test to fail.
    """
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def make_unit(
    db: Session, serial: str, months: int = 60, product: DealerProduct | None = None
) -> DealerUnit:
    """A dealer label that was printed before the scanner was retired.

    Nothing mints these any more — the endpoint is gone — but the rows are the
    record of what went out on mattresses, and the public and admin lookups
    still answer questions about them. `serial` is the token printed on the
    DEALER label, not the factory's; the two are unrelated.
    """
    if product is None:
        product = make_product(db, name=f"Model {uuid.uuid4().hex[:6]}", months=months)
    unit = DealerUnit(product_id=product.id, token=serial, status="active")
    db.add(unit)
    db.flush()
    return unit


def new_serial() -> str:
    return str(uuid.uuid4())


def make_legacy_warranty(
    db: Session,
    *,
    dealer: Dealer | None = None,
    serial: str | None = None,
    customer: Customer | None = None,
    customer_phone: str = "+919812345678",
    customer_name: str = "Asha Kumar",
    model_name: str = "GoodBed HR Foam",
    months: int = 60,
    status: str = "active",
    source: str = "dealer",
    invoice_ref: str | None = None,
    registered_at: datetime | None = None,
) -> Warranty:
    """A warranty as it exists from BEFORE the dropdown replaced the scanner.

    Registration cannot produce one of these any more — every row it writes
    now has serial NULL — but the table is full of them and they are still under
    warranty for years. Everything a customer or the support desk reaches a
    warranty BY is still addressed by serial: public lookup, claims, the admin
    serial screen. Building the row directly is the only way left to give those
    paths something to find, and it is honest about what they now serve.

    Written straight to the table rather than through a service, because the
    service that wrote rows like this no longer exists.
    """
    if customer is None:
        customer = Customer(phone=customer_phone, name=customer_name)
        db.add(customer)
        db.flush()
    start = business_today()
    warranty = Warranty(
        serial=serial or new_serial(),
        model_name=model_name,
        warranty_months=months,
        dealer_id=dealer.id if dealer else None,
        customer_id=customer.id,
        invoice_ref=invoice_ref,
        warranty_start_date=start,
        warranty_end_date=add_months(start, months),
        status=status,
        source=source,
        registered_at=registered_at or datetime.now(UTC),
    )
    db.add(warranty)
    db.flush()
    # Every warranty the service ever wrote opened its own history, and the admin
    # serial screen renders that timeline. A row without one is a shape the table
    # has never actually held.
    db.add(
        WarrantyEvent(
            warranty_id=warranty.id,
            event="registered",
            from_status=None,
            to_status=status,
            actor_type="dealer_staff",
            event_metadata={"serial": warranty.serial},
        )
    )
    db.flush()
    return warranty
