"""Seed the DEALER programme for local development.

Independent of seed_dev.py, which seeds the worker programme. The two share no
tables, so they can be run in either order or on their own.

    uv run python -m app.scripts.seed_dealer_dev
"""

import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.dealer.models.admin import DealerAdmin
from app.dealer.models.allocation import Allocation
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.product import DealerProduct
from app.dealer.models.reward import Reward
from app.dealer.models.unit import DealerUnit
from app.dealer.services import qr
from app.dealer.services.ledger import set_rate

ADMIN_EMAIL = "dealer-admin@goodbed.test"
ADMIN_PASSWORD = "dealer-rewards-dev"


def main() -> int:
    if settings.env != "dev" and "--force" not in sys.argv:
        print("Refusing to seed outside dev without --force")
        return 1

    with SessionLocal() as db:
        admin = db.execute(
            select(DealerAdmin).where(DealerAdmin.email == ADMIN_EMAIL)
        ).scalar_one_or_none()
        if admin is None:
            admin = DealerAdmin(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                name="Dealer Owner",
                role="owner",
            )
            db.add(admin)
            db.flush()

        specs = [("GoodBed HR Foam 6in", 60, 50), ("GoodBed Ortho Plus 8in", 84, 75)]
        products: list[DealerProduct] = []
        for name, months, points in specs:
            product = db.execute(
                select(DealerProduct).where(DealerProduct.name == name)
            ).scalar_one_or_none()
            if product is None:
                product = DealerProduct(
                    name=name,
                    description="Seeded for local development",
                    warranty_months=months,
                    is_active=True,
                )
                db.add(product)
                db.flush()
                # Serials come from the real batch service, so the seeded data
                # looks exactly like data an admin would produce.
                qr.generate_batch(
                    db,
                    product_id=product.id,
                    quantity=8,
                    label="dev seed",
                    admin_id=admin.id,
                )
            set_rate(db, product_id=product.id, points_per_registration=points)
            products.append(product)

        dealers = []
        for code, name, city, phones in [
            ("D001", "Shop One", "Nagpur", ["+919000000001", "+919000000002"]),
            ("D002", "Shop Two", "Pune", ["+919000000003"]),
        ]:
            dealer = db.execute(select(Dealer).where(Dealer.code == code)).scalar_one_or_none()
            if dealer is None:
                dealer = Dealer(code=code, name=name, city=city)
                db.add(dealer)
                db.flush()
                for i, phone in enumerate(phones):
                    db.add(
                        DealerStaff(
                            dealer_id=dealer.id,
                            phone=phone,
                            name=f"{name} staff {i + 1}",
                            role="owner" if i == 0 else "staff",
                        )
                    )
            dealers.append(dealer)
        db.flush()

        # Split the unallocated serials between the two shops, leaving a few
        # spare so the compliance screen has something to show.
        free = list(
            db.execute(
                select(DealerUnit)
                .where(
                    DealerUnit.status == "active",
                    DealerUnit.token.notin_(select(Allocation.serial)),
                )
                .limit(12)
            ).scalars()
        )
        for i, unit in enumerate(free):
            db.add(
                Allocation(
                    serial=unit.token,
                    dealer_id=dealers[i % len(dealers)].id,
                    status="allocated",
                )
            )

        if db.execute(select(Reward)).first() is None:
            db.add_all(
                [
                    Reward(name="Cotton bedsheet set", points_cost=250, sort_order=1),
                    Reward(name="Pillow pair", points_cost=400, sort_order=2),
                    Reward(name="₹1,000 voucher", points_cost=1000, sort_order=3),
                ]
            )
        db.commit()

        sample = db.execute(
            select(DealerUnit.token)
            .join(Allocation, Allocation.serial == DealerUnit.token)
            .limit(1)
        ).scalar_one_or_none()

        print("  Dealer Rewards — dev data ready")
        print("  " + "-" * 60)
        print(f"  Dealer admin   {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print("  Dealer staff   +919000000001 / +919000000002 (D001), +919000000003 (D002)")
        print(f"  Products       {', '.join(p.name for p in products)}")
        print(f"  Scan this      {sample}")
        print()
        print("  These serials are DEALER labels. The worker programme's QR codes")
        print("  are different tokens entirely and will not scan in the dealer app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
