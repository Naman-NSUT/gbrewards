"""Dev seed: an admin, a product, and a batch of active units.

Usage: uv run python -m app.scripts.seed_dev [quantity]
Prints the created unit tokens so you can exercise /scan/claim.
"""

import sys
import uuid

from app.core.config import settings
from app.core.security import hash_secret
from app.db.session import SessionLocal
from app.models.admin import Admin
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.models.qr_batch import QrBatch


def main(quantity: int = 5) -> None:
    if settings.env != "dev":
        raise SystemExit("seed_dev only runs with ENV=dev")

    with SessionLocal() as db:
        admin = db.query(Admin).filter(Admin.email == "admin@example.com").one_or_none()
        if admin is None:
            admin = Admin(
                email="admin@example.com",
                password_hash=hash_secret("admin12345"),
                name="Seed Admin",
                role="owner",
            )
            db.add(admin)
            db.flush()

        product = Product(name="Seed Widget", description="Dev seed", points_value=100)
        db.add(product)
        db.flush()

        batch = QrBatch(
            product_id=product.id,
            quantity=quantity,
            created_by_admin_id=admin.id,
            label="dev seed batch",
        )
        db.add(batch)
        db.flush()

        tokens = []
        for _ in range(quantity):
            token = str(uuid.uuid4())
            db.add(
                ProductUnit(
                    product_id=product.id,
                    token=token,
                    status="active",
                    batch_id=batch.id,
                )
            )
            tokens.append(token)
        db.commit()

    print("admin: admin@example.com / admin12345")
    print(f"product: {product.name} ({product.points_value} pts)")
    print("unit tokens:")
    for t in tokens:
        print(f"  {t}")


if __name__ == "__main__":
    qty = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    main(qty)
