import threading

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.models.ledger_entry import LedgerEntry
from app.models.product import Product
from app.models.product_unit import ProductUnit
from app.models.user import User
from app.services.claim import claim

N = 20


def test_parallel_claims_credit_exactly_once(db_truncate: sessionmaker) -> None:
    # Seed one active unit and N users in a committed transaction.
    setup = db_truncate()
    product = Product(name="Widget", points_value=100)
    setup.add(product)
    setup.flush()
    unit = ProductUnit(product_id=product.id, token="race-token", status="active")
    setup.add(unit)
    users = [User(phone=f"+9199000{i:05d}", name=f"U{i}") for i in range(N)]
    setup.add_all(users)
    setup.commit()
    user_ids = [u.id for u in users]
    unit_id = unit.id
    setup.close()

    barrier = threading.Barrier(N)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(user_id: object) -> None:
        session = db_truncate()
        try:
            barrier.wait()
            claim(session, user_id=user_id, token="race-token")
            with lock:
                outcomes.append("won")
        except AppError as exc:
            with lock:
                outcomes.append(exc.code)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one winner; everyone else saw already_claimed.
    assert outcomes.count("won") == 1
    assert outcomes.count("already_claimed") == N - 1

    verify = db_truncate()
    credit_count = verify.execute(
        select(func.count()).select_from(LedgerEntry).where(LedgerEntry.product_unit_id == unit_id)
    ).scalar_one()
    assert credit_count == 1

    claimed_unit = verify.get(ProductUnit, unit_id)
    assert claimed_unit is not None
    assert claimed_unit.status == "claimed"
    assert claimed_unit.claimed_by_user_id in user_ids
    verify.close()
