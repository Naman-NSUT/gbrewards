"""Spending points — the half of the ledger that can lose the client money.

A registration credit is bounded by the units the brand allocated. A redemption
is bounded only by our own arithmetic, so every test here is a way that
arithmetic could pay out points the dealer does not have:

  * a hold that does not reduce what is spendable
  * two requests racing on one balance
  * an approval that debits twice
  * a rejection that forgets to release
  * one dealership touching another's queue
  * an approval that ignores a clawback landing after the request
"""

import threading
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.errors import AppError, register_exception_handlers
from app.core.security import create_access_token
from app.dealer.api.dealer import rewards as rewards_router
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.reward import Redemption, Reward
from app.dealer.models.warranty import Warranty
from app.dealer.services import ledger, registration
from app.dealer.services import redemption as redemption_svc
from app.dealer.services import warranty as warranty_svc
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_product,
    make_rate,
    make_staff,
    make_unit,
    new_serial,
)


def _reward(
    db: Session,
    *,
    name: str = "Bosch cordless drill",
    points: int = 100,
    stock: int | None = None,
    active: bool = True,
) -> Reward:
    reward = Reward(
        name=name,
        description="Dealer catalogue item",
        points_cost=points,
        stock=stock,
        is_active=active,
    )
    db.add(reward)
    db.flush()
    return reward


def _earn(db: Session, staff: DealerStaff, dealer: Dealer, count: int, points: int = 50) -> int:
    """Earn points the only way a dealer can: by registering real sales."""
    # One product priced at `points`, reused for every sale below, so the rate
    # and the units actually belong together now that points are per-product.
    product = make_product(db)
    make_rate(db, points, product=product)
    for i in range(count):
        serial = new_serial()
        make_unit(db, serial, product=product)
        registration.register(
            db,
            staff=staff,
            raw_serial=serial,
            customer_phone=f"+91981{i:07d}",
            customer_name=f"Customer {i}",
            invoice_ref=f"INV-{i}",
        )
    db.flush()
    return count * points


# --- The hold --------------------------------------------------------------


def test_a_request_reduces_available_but_never_the_balance(db):
    """The hold is the pending row itself. Nothing reaches the ledger yet."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    _earn(db, staff, dealer, count=3)  # 150
    reward = _reward(db, points=100)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()

    assert ledger.balance(db, dealer.id) == 150, "points are not spent until an admin approves"
    assert ledger.pending(db, dealer.id) == 100
    assert ledger.available(db, dealer.id) == 50
    assert db.query(LedgerEntry).filter_by(type="redemption_debit").count() == 0
    # Price and name frozen onto the request at the moment it was made.
    assert redemption.points == 100
    assert redemption.reward_name == "Bosch cordless drill"
    assert redemption.status == "pending"


def test_a_catalogue_edit_cannot_reprice_a_queued_request(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    _earn(db, staff, dealer, count=3)
    reward = _reward(db, points=100)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()

    reward.points_cost = 400
    reward.name = "Bosch cordless drill (2026 model)"
    db.commit()
    db.refresh(redemption)

    assert redemption.points == 100
    assert redemption.reward_name == "Bosch cordless drill"
    assert ledger.available(db, dealer.id) == 50


def test_a_second_request_cannot_spend_the_points_already_held(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    _earn(db, staff, dealer, count=3)  # 150
    reward = _reward(db, points=100)
    db.commit()

    redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()

    with pytest.raises(AppError) as exc:
        redemption_svc.create(db, staff=staff, reward_id=reward.id)
    assert exc.value.code == "insufficient_points"
    assert exc.value.details["available"] == 50
    db.rollback()
    assert db.query(Redemption).count() == 1


# --- Concurrency -----------------------------------------------------------


def test_parallel_requests_cannot_over_commit_the_same_balance(session_maker):
    """Real threads, real connections, real Postgres — not a simulated race.

    Eight phones in one shop tapping Redeem at the same instant on a balance
    that covers exactly one reward.
    """
    setup = session_maker()
    dealer = make_dealer(setup)
    staff = make_staff(setup, dealer)
    _earn(setup, staff, dealer, count=3)  # 150
    reward = _reward(setup, points=100)
    setup.commit()
    staff_id, reward_id, dealer_id = staff.id, reward.id, dealer.id
    setup.close()

    n = 8
    barrier = threading.Barrier(n)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        session = session_maker()
        try:
            local_staff = session.get(DealerStaff, staff_id)
            barrier.wait()
            redemption_svc.create(session, staff=local_staff, reward_id=reward_id)
            session.commit()
            with lock:
                outcomes.append("created")
        except AppError as exc:
            session.rollback()
            with lock:
                outcomes.append(exc.code)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            with lock:
                outcomes.append(type(exc).__name__)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    verify = session_maker()
    pending = verify.query(Redemption).filter_by(status="pending").all()
    assert len(pending) == 1, f"expected exactly one hold, got {len(pending)}: {outcomes}"
    assert outcomes.count("created") == 1, f"outcomes={outcomes}"
    assert set(outcomes) - {"created"} == {"insufficient_points"}, f"outcomes={outcomes}"
    assert ledger.balance(verify, dealer_id) == 150
    assert ledger.available(verify, dealer_id) == 50
    verify.close()


def test_a_request_cannot_commit_a_balance_another_request_is_already_spending(
    session_maker, monkeypatch
):
    """The same race as above, but with the interleaving pinned instead of raced.

    The barrier test only catches the bug when the OS happens to schedule two
    threads between the balance read and the insert — on this machine it misses
    roughly half the time, which makes it a poor guard for the one invariant
    that decides whether points can be spent twice. Here the first request is
    frozen after it has read the balance and before it has committed, and the
    second is run to completion inside that window. Remove the SELECT ... FOR
    UPDATE in redemption._lock_dealer and this fails every single time.
    """
    setup = session_maker()
    dealer = make_dealer(setup)
    staff = make_staff(setup, dealer)
    _earn(setup, staff, dealer, count=3)  # 150
    reward = _reward(setup, points=100)
    setup.commit()
    staff_id, reward_id, dealer_id = staff.id, reward.id, dealer.id
    setup.close()

    real_available = ledger.available
    has_read = threading.Event()
    may_continue = threading.Event()

    def gated_available(session, dealer_id):  # type: ignore[no-untyped-def]
        value = real_available(session, dealer_id)
        # Only the first request is held open; the second must run freely.
        if threading.current_thread().name == "first-request":
            has_read.set()
            may_continue.wait(10)
        return value

    monkeypatch.setattr(ledger, "available", gated_available)

    outcomes: dict[str, str] = {}

    def attempt(label: str) -> None:
        session = session_maker()
        try:
            local_staff = session.get(DealerStaff, staff_id)
            redemption_svc.create(session, staff=local_staff, reward_id=reward_id)
            session.commit()
            outcomes[label] = "created"
        except AppError as exc:
            session.rollback()
            outcomes[label] = exc.code
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            outcomes[label] = type(exc).__name__
        finally:
            session.close()

    first = threading.Thread(target=attempt, args=("first",), name="first-request")
    second = threading.Thread(target=attempt, args=("second",), name="second-request")

    first.start()
    assert has_read.wait(10), "the first request never reached the balance check"

    second.start()
    # The second request now either blocks on the dealer row lock (correct) or
    # sails through on a balance the first request has already committed to
    # spending (the bug). One second is far longer than the query needs.
    second.join(timeout=1.0)
    may_continue.set()
    first.join(timeout=10)
    second.join(timeout=10)

    assert outcomes["first"] == "created", outcomes
    assert outcomes["second"] == "insufficient_points", outcomes

    verify = session_maker()
    assert verify.query(Redemption).filter_by(status="pending").count() == 1
    assert real_available(verify, dealer_id) == 50
    verify.close()


# --- Approval --------------------------------------------------------------


def test_approval_writes_exactly_one_debit_and_takes_one_unit_of_stock(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    _earn(db, staff, dealer, count=3)  # 150
    reward = _reward(db, points=100, stock=2)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()

    redemption_svc.approve(
        db, redemption=redemption, admin_id=admin.id, note="Couriered on Tuesday"
    )
    db.commit()

    debits = db.query(LedgerEntry).filter_by(type="redemption_debit").all()
    assert len(debits) == 1
    assert debits[0].amount == -100
    assert debits[0].redemption_id == redemption.id
    assert debits[0].admin_id == admin.id

    assert redemption.status == "approved"
    assert redemption.processed_by_admin_id == admin.id
    assert redemption.processed_at is not None
    assert reward.stock == 1
    # The hold is gone because the row is no longer pending; the debit replaced it.
    assert ledger.balance(db, dealer.id) == 50
    assert ledger.pending(db, dealer.id) == 0
    assert ledger.available(db, dealer.id) == 50

    with pytest.raises(AppError) as exc:
        redemption_svc.approve(db, redemption=redemption, admin_id=admin.id)
    assert exc.value.code == "not_pending"
    db.rollback()


def test_the_database_rejects_a_second_debit_for_one_redemption(db):
    """The guarantee must not depend on the service layer being correct."""
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    _earn(db, staff, dealer, count=3)
    reward = _reward(db, points=100)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    redemption_svc.approve(db, redemption=redemption, admin_id=admin.id)
    db.commit()

    with pytest.raises(IntegrityError):
        # uq_ledger_redemption_debit, bypassing every service-level check.
        ledger.add_entry(
            db,
            dealer_id=dealer.id,
            amount=-100,
            type=ledger.REDEMPTION_DEBIT,
            redemption_id=redemption.id,
        )
    db.rollback()

    assert db.query(LedgerEntry).filter_by(type="redemption_debit").count() == 1
    assert ledger.balance(db, dealer.id) == 50


def test_approval_is_refused_once_a_clawback_has_taken_the_points_back(db):
    """The balance at request time is not the balance at approval time.

    A voided registration claws its credit back. Approving on the strength of a
    balance that no longer exists is what makes register-fake-then-redeem pay.
    """
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    _earn(db, staff, dealer, count=2)  # 100
    reward = _reward(db, points=100)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()
    assert ledger.available(db, dealer.id) == 0

    warranty = (
        db.query(Warranty).filter_by(dealer_id=dealer.id).order_by(Warranty.created_at).first()
    )
    warranty_svc.void(
        db,
        warranty=warranty,
        reason="Customer returned the mattress",
        actor_type="admin",
        actor_id=admin.id,
    )
    db.commit()
    assert ledger.balance(db, dealer.id) == 50

    with pytest.raises(AppError) as exc:
        redemption_svc.approve(db, redemption=redemption, admin_id=admin.id)
    assert exc.value.code == "insufficient_points"
    assert exc.value.details["balance"] == 50
    db.rollback()

    assert db.query(LedgerEntry).filter_by(type="redemption_debit").count() == 0
    assert redemption.status == "pending", "the request stays queued for the admin to reject"


def test_approval_is_refused_when_the_last_unit_of_stock_is_gone(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    _earn(db, staff, dealer, count=3)
    reward = _reward(db, points=100, stock=1)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()

    reward.stock = 0  # an admin corrected the count in the meantime
    db.commit()

    with pytest.raises(AppError) as exc:
        redemption_svc.approve(db, redemption=redemption, admin_id=admin.id)
    assert exc.value.code == "out_of_stock"
    db.rollback()
    assert db.query(LedgerEntry).filter_by(type="redemption_debit").count() == 0


# --- Release ---------------------------------------------------------------


def test_rejection_releases_the_hold_and_writes_no_ledger_row(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    _earn(db, staff, dealer, count=3)  # 150
    reward = _reward(db, points=100)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()
    assert ledger.available(db, dealer.id) == 50

    redemption_svc.reject(
        db, redemption=redemption, admin_id=admin.id, reason="Item discontinued by supplier"
    )
    db.commit()

    assert redemption.status == "rejected"
    assert redemption.processed_by_admin_id == admin.id
    assert "Item discontinued by supplier" in (redemption.note or "")
    assert ledger.pending(db, dealer.id) == 0
    assert ledger.available(db, dealer.id) == 150, "the hold is released by leaving pending"
    assert ledger.balance(db, dealer.id) == 150
    assert db.query(LedgerEntry).count() == 3, "only the three registration credits"


def test_rejection_requires_a_reason(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    admin = make_admin(db)
    _earn(db, staff, dealer, count=3)
    reward = _reward(db, points=100)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()

    with pytest.raises(AppError) as exc:
        redemption_svc.reject(db, redemption=redemption, admin_id=admin.id, reason="   ")
    assert exc.value.code == "reason_required"
    db.rollback()
    assert redemption.status == "pending"


def test_cancelling_releases_the_hold_and_frees_the_points_to_be_spent_again(db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    _earn(db, staff, dealer, count=3)  # 150
    reward = _reward(db, points=100)
    db.commit()

    first = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()
    redemption_svc.cancel(db, redemption=first, staff=staff)
    db.commit()

    assert first.status == "cancelled"
    assert ledger.available(db, dealer.id) == 150
    assert db.query(LedgerEntry).filter_by(type="redemption_debit").count() == 0

    # The freed points are spendable again.
    second = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()
    assert second.id != first.id
    assert ledger.available(db, dealer.id) == 50


# --- Scoping ---------------------------------------------------------------


def test_a_dealer_cannot_cancel_another_dealers_request(db):
    dealer_a = make_dealer(db, code="D001")
    dealer_b = make_dealer(db, code="D002", name="Shop Two")
    staff_a = make_staff(db, dealer_a, phone="+919000000001")
    staff_b = make_staff(db, dealer_b, phone="+919000000002")
    _earn(db, staff_a, dealer_a, count=3)
    reward = _reward(db, points=100)
    db.commit()

    redemption = redemption_svc.create(db, staff=staff_a, reward_id=reward.id)
    db.commit()

    with pytest.raises(AppError) as exc:
        redemption_svc.cancel(db, redemption=redemption, staff=staff_b)
    # 404, not 403: dealer B must not learn that this id exists.
    assert exc.value.status_code == 404

    with pytest.raises(AppError) as exc:
        redemption_svc.get_for_dealer(db, redemption_id=redemption.id, dealer_id=dealer_b.id)
    assert exc.value.status_code == 404

    db.rollback()
    assert redemption.status == "pending"
    assert ledger.available(db, dealer_a.id) == 50


# --- Through the HTTP layer ------------------------------------------------


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    """A minimal app carrying only this router.

    Mounted here rather than relying on app.api.v1.__init__ so these tests pin
    the router's own behaviour regardless of how it is wired up.
    """
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(rewards_router.router, prefix="/api/v1/dealer")

    def _get_db():  # type: ignore[no-untyped-def]
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def two_shops(db):  # type: ignore[no-untyped-def]
    dealer_a = make_dealer(db, code="D001")
    dealer_b = make_dealer(db, code="D002", name="Shop Two")
    staff_a = make_staff(db, dealer_a, phone="+919000000001")
    staff_b = make_staff(db, dealer_b, phone="+919000000002")
    _earn(db, staff_a, dealer_a, count=3)  # 150 for A, nothing for B
    reward = _reward(db, points=100)
    _reward(db, name="Insulated lunch box", points=1000)
    redemption = redemption_svc.create(db, staff=staff_a, reward_id=reward.id)
    db.commit()
    return {
        "redemption": redemption,
        "a": {"Authorization": f"Bearer {create_access_token(str(staff_a.id), aud='dealer')}"},
        "b": {"Authorization": f"Bearer {create_access_token(str(staff_b.id), aud='dealer')}"},
    }


def test_a_staff_member_only_sees_their_own_dealerships_redemptions(client, two_shops):
    mine = client.get("/api/v1/dealer/redemptions", headers=two_shops["a"])
    assert mine.status_code == 200, mine.text
    assert mine.json()["total"] == 1
    assert mine.json()["items"][0]["id"] == str(two_shops["redemption"].id)

    theirs = client.get("/api/v1/dealer/redemptions", headers=two_shops["b"])
    assert theirs.status_code == 200
    assert theirs.json()["total"] == 0
    assert theirs.json()["items"] == []


def test_cancelling_another_dealerships_request_is_a_404_over_http(client, two_shops, db):
    redemption_id = two_shops["redemption"].id

    resp = client.post(f"/api/v1/dealer/redemptions/{redemption_id}/cancel", headers=two_shops["b"])
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
    db.expire_all()
    assert db.get(Redemption, redemption_id).status == "pending"

    mine = client.post(f"/api/v1/dealer/redemptions/{redemption_id}/cancel", headers=two_shops["a"])
    assert mine.status_code == 200
    assert mine.json()["status"] == "cancelled"


def test_the_catalogue_marks_each_reward_against_available_points(client, two_shops):
    resp = client.get("/api/v1/dealer/rewards", headers=two_shops["a"])
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["balance"] == 150
    assert body["pending"] == 100
    assert body["available"] == 50
    by_cost = {item["points_cost"]: item for item in body["items"]}
    # 100-point reward is unaffordable NOW because 100 of the 150 are held.
    assert by_cost[100]["affordable"] is False
    assert by_cost[100]["short_by"] == 50
    assert by_cost[1000]["affordable"] is False
    assert by_cost[1000]["short_by"] == 950


def test_an_unknown_redemption_id_is_a_404_not_a_500(client, two_shops):
    resp = client.post(f"/api/v1/dealer/redemptions/{uuid.uuid4()}/cancel", headers=two_shops["a"])
    assert resp.status_code == 404
