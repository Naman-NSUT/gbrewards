"""The approval queue must not multiply its rows, and must not invent a seller.

This queue IS the non-compliance report: an account manager phones a shop about
every row in it. Two properties therefore have to hold, and neither is visible
in a test with a single dealer on the books — an unconstrained join multiplies
one row by one, and the only dealer available to blame is the right one by luck.

  * one pending warranty is ONE row and counts ONCE, whatever the size of the
    dealer network
  * an UNATTRIBUTED self-registration — the customer never said where they
    bought it — is shown as unattributed, not pinned on whichever shop the
    query happened to pair it with. A shop named on that row gets phoned about
    a sale it may never have made.

Three dealerships, on purpose: with three, a cross join returns 3x the rows and
inflates the total by 3, which is the difference between a report and a libel.
"""

import warnings
from datetime import timedelta

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SAWarning

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from app.dealer.api.admin._common import count_of
from app.dealer.api.admin.approvals import _queue_select
from app.dealer.services import registration, self_registration
from app.dealer.services.warranty_dates import business_today
from app.main import create_app
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_priced_unit,
    make_staff,
    new_serial,
)

PREFIX = "/api/v1/dealer-admin"


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    def _get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fake
    with TestClient(app) as c:
        yield c


@pytest.fixture
def h(db):  # type: ignore[no-untyped-def]
    admin = make_admin(db, role="owner")
    db.commit()
    token = create_access_token(str(admin.id), "dealer_admin", {"role": admin.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def queue(db):  # type: ignore[no-untyped-def]
    """Three dealerships and three pending decisions, one of each kind.

    Returns the ids of the warranty each dealership is answerable for, plus the
    one nobody is.
    """
    dealers = [
        make_dealer(db, code="D001", name="Sunrise Beds"),
        make_dealer(db, code="D002", name="Moonlight Mattress"),
        make_dealer(db, code="D003", name="Comfort Corner"),
    ]

    # 1. D001 recorded the sale but claimed a date well outside the grace window
    staff = make_staff(db, dealers[0], phone="+919000000101")
    backdated_serial = new_serial()
    make_priced_unit(db, backdated_serial, 50)
    backdated = registration.register(
        db,
        staff=staff,
        raw_serial=backdated_serial,
        customer_phone="+919812345001",
        customer_name="Asha Kumar",
        invoice_ref="INV-1",
        invoice_date=business_today() - timedelta(days=400),
    ).warranty
    assert backdated.status == "pending_backdate"

    # 2. a customer registered their own purchase and named D002
    named = self_registration.submit(
        db,
        raw_serial=new_serial(),
        customer_phone="+919812345002",
        customer_name="Bhavna Rao",
        purchase_date=business_today() - timedelta(days=20),
        dealer_hint="D002",
    )
    assert named.dealer is not None and named.dealer.id == dealers[1].id

    # 3. a customer who did not say where they bought it. Nobody is answerable.
    unattributed = self_registration.submit(
        db,
        raw_serial=new_serial(),
        customer_phone="+919812345003",
        customer_name="Chetan Iyer",
        purchase_date=business_today() - timedelta(days=15),
    )
    assert unattributed.dealer is None

    db.commit()
    return {
        "dealers": dealers,
        "backdated_id": str(backdated.id),
        "named_id": str(named.warranty.id),
        "unattributed_id": str(unattributed.warranty.id),
    }


def test_three_pending_decisions_are_three_rows_not_nine(client, h, queue):
    body = client.get(f"{PREFIX}/approvals", headers=h).json()

    ids = [item["id"] for item in body["items"]]
    assert sorted(ids) == sorted(
        [queue["backdated_id"], queue["named_id"], queue["unattributed_id"]]
    )
    assert len(ids) == len(set(ids)), "each pending warranty appears once, not once per dealership"
    # The badge an admin works down. Inflated by the dealer count, it tells them
    # to keep looking for work that does not exist.
    assert body["total"] == 3


def test_an_unattributed_self_registration_blames_nobody(client, h, queue):
    body = client.get(f"{PREFIX}/approvals", headers=h).json()
    items = {item["id"]: item for item in body["items"]}

    orphan = items[queue["unattributed_id"]]
    assert orphan["dealer"] is None, "no shop may be named on a sale the customer never placed"
    assert orphan["dealer_source"] is None

    # The two rows that DO name a shop name the right one, from the warranty.
    assert items[queue["named_id"]]["dealer"]["code"] == "D002"
    assert items[queue["named_id"]]["dealer_source"] == "warranty"
    assert items[queue["backdated_id"]]["dealer"]["code"] == "D001"
    assert items[queue["backdated_id"]]["dealer_source"] == "warranty"


def test_filtering_by_dealer_returns_only_that_dealers_pending_work(client, h, queue):
    d002 = queue["dealers"][1]
    body = client.get(f"{PREFIX}/approvals?dealer_id={d002.id}", headers=h).json()

    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [queue["named_id"]]


def test_the_queue_query_has_no_cartesian_product(db, queue):
    """No unconstrained FROM element, proven at compile time.

    compiled_cache is disabled so the statement is compiled here rather than
    replayed from the engine cache — the from-linter only speaks during a
    compile, and an earlier test in the same process would otherwise silence it.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        db.execute(_queue_select(), execution_options={"compiled_cache": None}).all()
        count_of(db, _queue_select())

    cartesian = [
        str(w.message)
        for w in caught
        if issubclass(w.category, SAWarning) and "cartesian product" in str(w.message)
    ]
    assert cartesian == []
