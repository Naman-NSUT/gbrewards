"""One shop, one story: the dealer page and the compliance screen must agree.

An account manager opens the compliance screen, sees a shop near the top, and
clicks through to the dealer page before phoning them. If the two screens count
the same warranties differently, the call starts with the dealer being told a
number they can disprove — and the one number that must never be inflated is
the one that says they failed to record a sale.

The trap is that a customer self-registration carries the dealer's id too: the
customer named the shop they bought from. That row is EVIDENCE the shop did not
register the sale, so counting it as one of the shop's registrations credits
them for the very record that indicts them, and lets a shop that has gone
quiet look active because its CUSTOMERS are still registering.
"""

from datetime import UTC, datetime, timedelta

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from app.dealer.models.warranty import Warranty
from app.dealer.services import registration, self_registration
from app.dealer.services import warranty as warranty_svc
from app.dealer.services.warranty_dates import business_today
from app.main import create_app
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_priced_product,
    make_staff,
    new_invoice,
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


def _register(db, staff, *, when: datetime) -> Warranty:
    product = make_priced_product(db, 50)
    warranty = registration.register(
        db,
        staff=staff,
        product_id=product.id,
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
        # A fresh bill each time: one live warranty per (dealer, invoice), so
        # reusing one here would fail as a duplicate rather than as this test.
        invoice_ref=new_invoice(),
    ).warranty
    # Registration stamps 'now'. The dates are the whole point of this test, so
    # they are set explicitly rather than left to the order rows happened to be
    # inserted in.
    warranty.registered_at = when
    return warranty


@pytest.fixture
def shop(db):  # type: ignore[no-untyped-def]
    """One shop with a history that separates what it did from what it didn't.

    Two sales it recorded (one later voided, and it is the more recent of the
    two), and one sale its customer had to record — the most recent event on
    the account by a fortnight.
    """
    now = datetime.now(UTC)
    dealer = make_dealer(db, code="D100", name="Sunrise Beds")
    staff = make_staff(db, dealer, phone="+919000000201")

    kept = _register(db, staff, when=now - timedelta(days=40))
    voided = _register(db, staff, when=now - timedelta(days=20))
    warranty_svc.void(db, warranty=voided, reason="Customer returned the mattress")

    self_reg = self_registration.submit(
        db,
        raw_serial=new_serial(),
        customer_phone="+919812340000",
        customer_name="Bhavna Rao",
        purchase_date=business_today() - timedelta(days=6),
        dealer_hint="D100",
    )
    assert self_reg.dealer is not None and self_reg.dealer.id == dealer.id
    self_reg.warranty.registered_at = now - timedelta(days=5)

    db.commit()
    return {"dealer": dealer, "kept": kept, "voided": voided, "self_reg": self_reg.warranty}


def test_dealer_page_counts_what_the_shop_recorded_not_what_its_customers_did(client, h, shop):
    stats = client.get(f"{PREFIX}/dealers/{shop['dealer'].id}", headers=h).json()["stats"]

    # One live sale THE SHOP recorded. The self-registration names this shop but
    # is the proof they did not record it, so it must not be credited here.
    assert stats["warranties_registered"] == 1
    assert stats["warranties_voided"] == 1
    assert stats["self_registrations"] == 1


def test_a_quiet_shop_is_not_made_to_look_active_by_its_customers(client, h, shop):
    detail = client.get(f"{PREFIX}/dealers/{shop['dealer'].id}", headers=h).json()

    last_at = datetime.fromisoformat(detail["stats"]["last_registration_at"])
    # 40 days quiet, not 5: the newer rows are a voided sale and a registration
    # the customer made. Neither is this shop scanning a mattress.
    assert last_at == shop["kept"].registered_at
    assert last_at != shop["self_reg"].registered_at
    assert last_at != shop["voided"].registered_at


def test_both_admin_screens_tell_the_same_story_about_this_shop(client, h, shop):
    dealer_id = shop["dealer"].id
    stats = client.get(f"{PREFIX}/dealers/{dealer_id}", headers=h).json()["stats"]
    summary = client.get(f"{PREFIX}/compliance/dealers/{dealer_id}", headers=h).json()["summary"]

    assert stats["warranties_registered"] == summary["warranties_registered"]
    assert stats["self_registrations"] == summary["self_registrations"]
    assert stats["last_registration_at"] == summary["last_registration_at"]
    # And the drilldown lists exactly the row both screens are counting.
    drill = client.get(f"{PREFIX}/compliance/dealers/{dealer_id}", headers=h).json()
    assert [r["warranty_id"] for r in drill["self_registrations"]] == [str(shop["self_reg"].id)]
