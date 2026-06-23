import uuid

from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.models.user import User


def make_user(db: Session, *, phone: str | None = None, name: str = "Broker") -> User:
    user = User(phone=phone or f"+9199{uuid.uuid4().int % 10**8:08d}", name=name)
    db.add(user)
    db.flush()
    return user


def make_product(db: Session, *, name: str = "Widget", points_value: int = 100) -> Product:
    product = Product(name=name, points_value=points_value)
    db.add(product)
    db.flush()
    return product


def make_unit(
    db: Session,
    *,
    product: Product | None = None,
    status: str = "active",
    token: str | None = None,
) -> ProductUnit:
    if product is None:
        product = make_product(db)
    unit = ProductUnit(
        product_id=product.id,
        token=token or str(uuid.uuid4()),
        status=status,
    )
    db.add(unit)
    db.flush()
    return unit


def auth_headers(user: User) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(sub=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def make_admin(
    db: Session,
    *,
    email: str | None = None,
    password: str = "admin12345",
    role: str = "owner",
) -> Admin:
    from app.core.security import hash_secret

    admin = Admin(
        email=email or f"admin-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_secret(password),
        name="Test Admin",
        role=role,
    )
    db.add(admin)
    db.flush()
    return admin


def admin_headers(admin: Admin) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(sub=str(admin.id), aud="admin")
    return {"Authorization": f"Bearer {token}"}
