"""The admin side of redeeming: physical stock, and the one note column.

The dealer-facing half of this flow is covered in test_redemption.py. What is
covered here is the half where a back-office operator can lose the client real
money or real goods, and both losses came from the same cause — the admin router
carrying its own copy of the approval logic instead of calling the service:

  * STOCK. The router looked the reward up unlocked, and `_load_for_decision`
    locks the DEALERS row, which cannot serialise a counter shared BETWEEN
    dealerships. Two admins approving for two different shops take two different
    dealer locks, contend for nothing, both read the last unit as available, and
    two drills ship for one drill of stock.
  * THE NOTE. `dealer_redemptions.note` has two authors. The dealer writes
    "please send to the Andheri branch" when they request; the admin writes
    "dispatched via Bluedart" when they approve. The router assigned over the
    top of the dealer's instruction, so the warehouse packed the box with the
    delivery address already deleted.

Every decision here is driven through the real admin HTTP endpoints, because
that is the layer the bug lived in: the service functions were correct the whole
time and nothing called them.
"""

import contextlib
import threading
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token
from app.dealer.api.admin import rewards as admin_rewards
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.ledger_entry import LedgerEntry
from app.dealer.models.reward import Redemption, Reward
from app.dealer.services import ledger, registration
from app.dealer.services import redemption as redemption_svc
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_priced_product,
    make_staff,
    new_invoice,
)

PREFIX = "/api/v1/dealer-admin"


# --- Fixtures and helpers --------------------------------------------------


@pytest.fixture
def app(session_factory):  # type: ignore[no-untyped-def]
    """A minimal app carrying only the admin rewards router.

    Mounted directly rather than through create_app() so these tests pin this
    router's behaviour regardless of how the tree is wired, and so no lifespan,
    Redis or rate limiter sits between a thread and the row lock it is racing.
    """
    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(admin_rewards.router, prefix=PREFIX)

    def _get_db():  # type: ignore[no-untyped-def]
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _get_db
    return application


@pytest.fixture
def client(app):  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        yield c


def _headers(admin) -> dict[str, str]:  # type: ignore[no-untyped-def]
    token = create_access_token(str(admin.id), "dealer_admin", {"role": admin.role})
    return {"Authorization": f"Bearer {token}"}


def _reward(
    db: Session, *, name: str = "Bosch cordless drill", points: int = 100, stock: int | None = None
) -> Reward:
    reward = Reward(
        name=name,
        description="Dealer catalogue item",
        points_cost=points,
        stock=stock,
        is_active=True,
    )
    db.add(reward)
    db.flush()
    return reward


def _shop(
    db: Session, index: int, *, sales: int = 1, points: int = 100
) -> tuple[Dealer, DealerStaff]:
    """A dealership holding real points — earned the only way points exist."""
    dealer = make_dealer(db, code=f"D{index:03d}", name=f"Shop {index}")
    staff = make_staff(db, dealer, phone=f"+9190000{index:05d}")
    product = make_priced_product(db, points, name=f"Model {index}")
    for sale in range(sales):
        registration.register(
            db,
            staff=staff,
            product_id=product.id,
            customer_phone=f"+9198{index:02d}{sale:05d}",
            customer_name=f"Customer {index}-{sale}",
            invoice_ref=new_invoice(),
        )
    db.flush()
    return dealer, staff


def _race_the_last_unit(app, db, *, admins: int) -> tuple[list[int], list[str]]:
    """Run `admins` approvals at one reward with stock=1, interleaving PINNED.

    A bare barrier would only catch this when the OS happened to schedule the
    threads between the unlocked stock read and the commit — it passes on a
    quiet machine and hides the bug. So the interleaving is forced instead:

      * approval 0 is frozen inside ledger.add_entry, at which point it has
        already read the stock (and, once fixed, already holds SELECT ... FOR
        UPDATE on the reward row);
      * every other approval is frozen at the same point until all of them have
        arrived, so none can commit before the others have read the stock.

    Unfixed, all of them read stock=1 and all of them approve. Fixed, the others
    never reach that rendezvous at all: they block on the reward row lock, and
    when approval 0 finally commits they wake to stock=0 and are refused. The
    barrier is therefore only ever satisfied by the broken code, so it can never
    hang the fixed code.
    """
    reward = _reward(db, points=100, stock=1)
    admin = make_admin(db)
    shops = [_shop(db, i) for i in range(admins)]
    db.commit()

    headers = _headers(admin)
    redemptions = []
    for _, staff in shops:
        redemptions.append(redemption_svc.create(db, staff=staff, reward_id=reward.id))
    db.commit()
    ids = [r.id for r in redemptions]

    real_add_entry = ledger.add_entry
    first_is_holding = threading.Event()
    release_first = threading.Event()
    rest = threading.Barrier(admins - 1) if admins > 1 else None

    def gated_add_entry(session, **kwargs):  # type: ignore[no-untyped-def]
        # Pinned on the redemption id, not the thread name: the endpoint body
        # runs on an anyio worker thread, not on the thread that made the call.
        if kwargs.get("redemption_id") == ids[0]:
            first_is_holding.set()
            release_first.wait(20)
        elif rest is not None:
            # Only reachable if the stock lock let more than one approval
            # through and then not all of them arrived. Carry on rather than
            # hang, and let the assertions report what actually happened.
            with contextlib.suppress(threading.BrokenBarrierError):
                rest.wait(timeout=20)
        return real_add_entry(session, **kwargs)

    ledger.add_entry = gated_add_entry  # type: ignore[assignment]
    statuses: dict[int, int] = {}
    codes: dict[int, str] = {}
    lock = threading.Lock()

    def approve(i: int) -> None:
        # One client per thread: an approval that blocks on a row lock must not
        # be able to hold up the request that is meant to be blocking it.
        resp = TestClient(app).post(
            f"{PREFIX}/redemptions/{ids[i]}/approve",
            headers=headers,
            json={"note": f"Approved by desk {i}"},
        )
        with lock:
            statuses[i] = resp.status_code
            codes[i] = "" if resp.status_code == 200 else resp.json()["error"]["code"]

    try:
        first = threading.Thread(target=approve, args=(0,))
        first.start()
        assert first_is_holding.wait(20), "the first approval never reached the ledger write"

        others = [threading.Thread(target=approve, args=(i,)) for i in range(1, admins)]
        for t in others:
            t.start()
        # Long enough for every other approval to have read the stock (broken)
        # or to have queued on the reward row lock (fixed).
        for t in others:
            t.join(timeout=1.5 / max(1, len(others)))

        release_first.set()
        for t in [first, *others]:
            t.join(timeout=30)
            assert not t.is_alive(), "an approval never finished"
    finally:
        ledger.add_entry = real_add_entry  # type: ignore[assignment]
        release_first.set()
        if rest is not None:
            rest.abort()

    db.rollback()
    db.expire_all()
    return [statuses[i] for i in range(admins)], [codes[i] for i in range(admins)]


# --- Stock -----------------------------------------------------------------


def test_two_admins_on_two_shops_cannot_both_take_the_last_unit(app, db):
    """The lock the router relied on is per-dealership. Stock is not."""
    statuses, codes = _race_the_last_unit(app, db, admins=2)

    assert statuses.count(200) == 1, f"one unit, one approval: statuses={statuses} codes={codes}"
    assert statuses.count(409) == 1, f"statuses={statuses} codes={codes}"
    assert set(codes) - {""} == {"out_of_stock"}, codes

    reward = db.query(Reward).one()
    assert reward.stock == 0, "stock went negative — two drills shipped for one drill"
    assert db.query(Redemption).filter_by(status="approved").count() == 1
    assert db.query(Redemption).filter_by(status="pending").count() == 1
    # The refused shop keeps every point it earned: nothing half-applied.
    refused = db.query(Redemption).filter_by(status="pending").one()
    assert ledger.balance(db, refused.dealer_id) == 100
    assert db.query(LedgerEntry).filter_by(type=ledger.REDEMPTION_DEBIT).count() == 1


def test_eight_admins_racing_one_unit_of_stock_ship_exactly_one(app, db):
    """Eight back-office desks, eight dealerships, one drill in the cupboard.

    This is the case that shipped: with the reward read unlocked, all eight
    approvals passed the `stock <= 0` guard and all eight decremented, so the
    warehouse owed seven drills it did not have and seven dealers had been
    charged for them.
    """
    statuses, codes = _race_the_last_unit(app, db, admins=8)

    assert statuses.count(200) == 1, f"statuses={statuses} codes={codes}"
    assert statuses.count(409) == 7, f"statuses={statuses} codes={codes}"
    assert set(codes) - {""} == {"out_of_stock"}, codes

    reward = db.query(Reward).one()
    assert reward.stock == 0, f"stock ended at {reward.stock}: units promised that do not exist"
    assert db.query(Redemption).filter_by(status="approved").count() == 1
    assert db.query(Redemption).filter_by(status="pending").count() == 7
    assert db.query(LedgerEntry).filter_by(type=ledger.REDEMPTION_DEBIT).count() == 1


# --- The note column -------------------------------------------------------


def test_an_admin_decision_never_destroys_the_dealers_delivery_instruction(client, db):
    """One column, two authors. The admin's note is appended, never assigned."""
    admin = make_admin(db)
    _, staff = _shop(db, 1, sales=3)
    reward = _reward(db, points=100)
    db.commit()

    instruction = "Please send to the Andheri branch, not the head office"
    approved = redemption_svc.create(db, staff=staff, reward_id=reward.id, note=instruction)
    rejected = redemption_svc.create(db, staff=staff, reward_id=reward.id, note=instruction)
    db.commit()
    h = _headers(admin)

    ok = client.post(
        f"{PREFIX}/redemptions/{approved.id}/approve",
        headers=h,
        json={"note": "Dispatched via Bluedart AWB 4471"},
    )
    assert ok.status_code == 200, ok.text
    note = ok.json()["redemption"]["note"]
    assert instruction in note, "the dealer's delivery address was overwritten by the admin note"
    assert "Bluedart AWB 4471" in note

    # Fulfilment is a third author on the same column and must not clobber either.
    done = client.post(
        f"{PREFIX}/redemptions/{approved.id}/mark-fulfilled",
        headers=h,
        json={"note": "Handed to courier, signed by Ravi"},
    )
    assert done.status_code == 200, done.text
    note = done.json()["redemption"]["note"]
    assert instruction in note, "fulfilment overwrote the dealer's delivery address"
    assert "Bluedart AWB 4471" in note, "fulfilment overwrote the approving admin's dispatch note"
    assert "signed by Ravi" in note

    no = client.post(
        f"{PREFIX}/redemptions/{rejected.id}/reject",
        headers=h,
        json={"reason": "Item discontinued by supplier"},
    )
    assert no.status_code == 200, no.text
    note = no.json()["redemption"]["note"]
    assert instruction in note, "a rejection erased what the dealer had asked for"
    assert "Item discontinued by supplier" in note


# --- The balance rule ------------------------------------------------------


def test_a_queued_request_is_checked_against_the_balance_not_the_other_holds(client, db):
    """Other pending requests are requests, not commitments.

    A clawback landing after three requests were made leaves a dealer with 70
    points and 180 points queued. Netting the other holds off would refuse all
    three and wedge the queue until someone rejected something the dealer might
    still want; checking the bare balance lets exactly the one they can afford
    through, and the next one then fails honestly on what the first one left.
    """
    admin = make_admin(db)
    dealer, staff = _shop(db, 1, sales=3, points=60)  # 180 earned
    reward = _reward(db, points=60)
    db.commit()

    queued = [redemption_svc.create(db, staff=staff, reward_id=reward.id) for _ in range(3)]
    db.commit()
    assert ledger.pending(db, dealer.id) == 180
    assert ledger.available(db, dealer.id) == 0

    # The clawback: two of the three registrations turned out to be fake.
    ledger.add_entry(
        db,
        dealer_id=dealer.id,
        amount=-110,
        type=ledger.ADMIN_DEBIT,
        admin_id=admin.id,
        reason="Clawback: registrations voided after audit",
    )
    db.commit()
    assert ledger.balance(db, dealer.id) == 70

    h = _headers(admin)
    first = client.post(f"{PREFIX}/redemptions/{queued[0].id}/approve", headers=h, json={})
    assert first.status_code == 200, (
        f"70 points cover a 60-point reward; refusing it strands the queue: {first.text}"
    )
    assert first.json()["points"]["balance"] == 10

    second = client.post(f"{PREFIX}/redemptions/{queued[1].id}/approve", headers=h, json={})
    assert second.status_code == 409, second.text
    error = second.json()["error"]
    assert error["code"] == "insufficient_points"
    # The other holds are still reported so the admin can see what else is
    # queued against the same balance — reported, never subtracted.
    assert error["details"] == {"balance": 10, "other_pending_holds": 60, "required": 60}

    db.rollback()
    db.expire_all()
    assert ledger.balance(db, dealer.id) == 10, "no rule may drive the balance negative"
    assert db.query(LedgerEntry).filter_by(type=ledger.REDEMPTION_DEBIT).count() == 1


# --- Contract --------------------------------------------------------------


def test_every_decision_returns_the_same_unchanged_response_shape(client, db):
    """A guard on the wire format the dealer admin panel already renders.

    Moving the logic behind the service must not add, drop or rename a field:
    the panel reads these keys directly and a rename is an invisible break.
    """
    admin = make_admin(db)
    _, staff = _shop(db, 1, sales=3)
    reward = _reward(db, points=100)
    db.commit()
    approved = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    rejected = redemption_svc.create(db, staff=staff, reward_id=reward.id)
    db.commit()
    h = _headers(admin)

    body = client.post(f"{PREFIX}/redemptions/{approved.id}/approve", headers=h, json={}).json()
    assert set(body) == {"redemption", "points"}
    assert set(body["redemption"]) == {
        "id",
        "dealer",
        "requested_by",
        "reward_id",
        "reward_name",
        "points",
        "status",
        "note",
        "processed_by_admin_id",
        "processed_at",
        "created_at",
    }
    assert set(body["redemption"]["dealer"]) == {"id", "code", "name", "status", "city"}
    assert set(body["redemption"]["requested_by"]) == {"id", "name", "phone", "role"}
    assert set(body["points"]) == {"balance", "pending", "available", "total_earned"}
    assert body["redemption"]["status"] == "approved"
    assert body["redemption"]["reward_id"] == str(reward.id)
    assert body["redemption"]["processed_by_admin_id"] == str(admin.id)
    approver = body["redemption"]["processed_by_admin_id"]
    approved_at = body["redemption"]["processed_at"]
    assert approved_at is not None

    other = make_admin(db, email="dispatch@example.com")
    db.commit()
    done = client.post(
        f"{PREFIX}/redemptions/{approved.id}/mark-fulfilled",
        headers=_headers(other),
        json={"note": "AWB 4471"},
    ).json()
    assert set(done) == set(body) and set(done["redemption"]) == set(body["redemption"])
    assert done["redemption"]["status"] == "fulfilled"
    # Fulfilment records who PACKED it, not who authorised the spend. Overwriting
    # these would erase the only record of who approved paying the points out.
    assert done["redemption"]["processed_by_admin_id"] == approver
    assert done["redemption"]["processed_at"] == approved_at

    no = client.post(
        f"{PREFIX}/redemptions/{rejected.id}/reject",
        headers=h,
        json={"reason": "Item discontinued by supplier"},
    ).json()
    assert set(no) == set(body) and set(no["redemption"]) == set(body["redemption"])
    assert no["redemption"]["status"] == "rejected"
    assert no["points"]["pending"] == 0

    missing = client.post(f"{PREFIX}/redemptions/{uuid.uuid4()}/approve", headers=h, json={})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "redemption_not_found"
