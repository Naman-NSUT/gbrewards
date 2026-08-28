"""The dealer back office, end to end over HTTP.

These routers shipped without tests. Rather than smoke-pinging each URL, each
test asserts the thing the screen exists to tell an operator — the compliance
ranking really ranks, a void really claws back, a suspended dealer really stops
earning — because a 200 that returns the wrong number is worse than a 500.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from app.dealer.services import ledger, registration
from app.main import create_app
from tests.dealer.factories import (
    make_admin,
    make_dealer,
    make_legacy_warranty,
    make_priced_product,
    make_product,
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

    # Rate limiters are per IP and every test calls from the same one, so a
    # shared real Redis would make later tests fail on counters earlier tests
    # ran up. A fresh fake per test keeps them independent.
    import fakeredis

    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fake
    with TestClient(app) as c:
        yield c


def _headers(admin) -> dict[str, str]:
    token = create_access_token(str(admin.id), "dealer_admin", {"role": admin.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner(db):  # type: ignore[no-untyped-def]
    a = make_admin(db, role="owner")
    db.commit()
    return a


@pytest.fixture
def h(owner):  # type: ignore[no-untyped-def]
    return _headers(owner)


def _sell(db, *, dealer=None, staff=None, points=50, invoice=None):
    """A real registration through the real service — the only way points exist."""
    dealer = dealer or make_dealer(db)
    staff = staff or make_staff(db, dealer)
    product = make_priced_product(db, points)
    result = registration.register(
        db,
        staff=staff,
        product_id=product.id,
        customer_phone="+919812345678",
        customer_name="Asha Kumar",
        invoice_ref=invoice or new_invoice(),
    )
    db.commit()
    return dealer, staff, result


# --- dealers ---------------------------------------------------------------


def test_dealer_directory_create_search_and_staff(client, db, h):
    created = client.post(
        f"{PREFIX}/dealers",
        headers=h,
        json={"code": "D900", "name": "Sunrise Beds", "city": "Nagpur"},
    )
    assert created.status_code == 201, created.text
    dealer_id = created.json()["id"]

    found = client.get(f"{PREFIX}/dealers?q=Sunrise", headers=h).json()
    assert any(d["code"] == "D900" for d in found["items"])

    staff = client.post(
        f"{PREFIX}/dealers/{dealer_id}/staff",
        headers=h,
        json={"name": "Ravi", "phone": "9812300001", "role": "owner"},
    )
    assert staff.status_code == 201, staff.text
    # stored E.164 so the shop's login matches what the app sends
    assert staff.json()["phone"] == "+919812300001"

    listed = client.get(f"{PREFIX}/dealers/{dealer_id}/staff", headers=h).json()
    assert len(listed) == 1


def test_suspending_a_dealer_needs_a_reason_and_stops_them_earning(client, db, h):
    dealer, staff, _ = _sell(db)

    bare = client.post(f"{PREFIX}/dealers/{dealer.id}/suspend", headers=h, json={"reason": " "})
    assert bare.status_code in (400, 422)

    ok = client.post(
        f"{PREFIX}/dealers/{dealer.id}/suspend",
        headers=h,
        json={"reason": "Registered sales that never happened"},
    )
    assert ok.status_code == 200, ok.text

    # a token minted before the suspension must stop working immediately
    token = create_access_token(str(staff.id), "dealer")
    blocked = client.get("/api/v1/dealer/points", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "dealer_inactive"

    client.post(f"{PREFIX}/dealers/{dealer.id}/reactivate", headers=h)
    assert (
        client.get(
            "/api/v1/dealer/points", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )


def test_dealer_points_and_ledger_views(client, db, h):
    dealer, _, _ = _sell(db, points=50)
    pts = client.get(f"{PREFIX}/dealers/{dealer.id}/points", headers=h).json()
    assert pts["balance"] == 50
    led = client.get(f"{PREFIX}/dealers/{dealer.id}/ledger", headers=h).json()
    assert led["items"][0]["amount"] == 50


def test_manual_adjustment_requires_a_reason_and_is_audited(client, db, h, owner):
    from app.dealer.models.audit_log import DealerAuditLog

    dealer = make_dealer(db)
    db.commit()

    refused = client.post(
        f"{PREFIX}/dealers/{dealer.id}/points/adjust",
        headers=h,
        json={"amount": 100, "reason": "   "},
    )
    assert refused.status_code in (400, 422)

    ok = client.post(
        f"{PREFIX}/dealers/{dealer.id}/points/adjust",
        headers=h,
        json={"amount": 100, "reason": "Goodwill for a mis-scanned unit"},
    )
    assert ok.status_code in (200, 201), ok.text
    assert ledger.balance(db, dealer.id) == 100
    assert db.query(DealerAuditLog).filter_by(action="adjust_points").count() == 1


# --- products --------------------------------------------------------------


def test_a_product_is_created_listed_and_retired(client, db, h):
    """The catalogue is now the whole of what a dealer may sell.

    Retiring a product is the only way the client takes a discontinued model off
    the counter dropdown, so is_active surviving a PATCH is a commercial control
    and not a flag.
    """
    created = client.post(
        f"{PREFIX}/products",
        headers=h,
        json={"name": "Ortho Plus", "warranty_months": 84, "is_active": True},
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]

    listed = client.get(f"{PREFIX}/products", headers=h).json()
    assert next(p for p in listed["items"] if p["id"] == pid)["warranty_months"] == 84

    patched = client.patch(
        f"{PREFIX}/products/{pid}",
        headers=h,
        json={"name": "Ortho Plus v2", "warranty_months": 84, "is_active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False


def test_printed_label_batches_are_still_readable_history(client, db, h):
    """Nothing mints a batch any more, so this list can only ever shrink.

    It stays because support still gets calls about a label somebody is holding,
    and the batch is how they find out when it was printed and for what.
    """
    assert client.get(f"{PREFIX}/batches", headers=h).status_code == 200


def test_warranty_search_detail_void_and_customer_edit(client, db, h):
    dealer, _, result = _sell(db, invoice="INV-SEARCH-1")
    wid = str(result.warranty.id)

    # The invoice number is what an operator has to search by now: it is the only
    # thing printed on both the shop's bill and the customer's copy.
    by_invoice = client.get(f"{PREFIX}/warranties?q=INV-SEARCH-1", headers=h).json()
    assert by_invoice["total"] == 1
    by_mobile = client.get(f"{PREFIX}/warranties?q=9812345678", headers=h).json()
    assert by_mobile["total"] == 1

    detail = client.get(f"{PREFIX}/warranties/{wid}", headers=h).json()
    assert detail["warranty"]["serial"] is None, "nothing was scanned"
    assert detail["warranty"]["invoice_ref"] == "INV-SEARCH-1"
    assert len(detail["events"]) >= 1

    edited = client.patch(
        f"{PREFIX}/warranties/{wid}/customer",
        headers=h,
        json={"name": "Asha Kumari", "reason": "Customer called to correct a typo"},
    )
    assert edited.status_code == 200, edited.text

    voided = client.post(
        f"{PREFIX}/warranties/{wid}/void",
        headers=h,
        json={"reason": "Mattress returned", "clawback": True},
    )
    assert voided.status_code == 200, voided.text
    assert ledger.balance(db, dealer.id) == 0, "void must claw the points back"


def test_void_without_a_reason_is_refused(client, db, h):
    _, _, result = _sell(db)
    resp = client.post(
        f"{PREFIX}/warranties/{result.warranty.id}/void", headers=h, json={"reason": " "}
    )
    assert resp.status_code in (400, 422)


# --- approvals -------------------------------------------------------------


def test_backdate_lands_in_approvals_and_pays_only_once_approved(client, db, h):
    from app.dealer.services.warranty_dates import business_today

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)
    result = registration.register(
        db,
        staff=staff,
        product_id=product.id,
        customer_phone="+919812345678",
        customer_name="Asha",
        invoice_ref="INV-1",
        invoice_date=business_today() - timedelta(days=400),
    )
    db.commit()
    assert result.warranty.status == "pending_backdate"

    count = client.get(f"{PREFIX}/approvals/count", headers=h).json()
    assert count["total"] >= 1
    queue = client.get(f"{PREFIX}/approvals", headers=h).json()
    assert any(i["id"] == str(result.warranty.id) for i in queue["items"])
    assert ledger.balance(db, dealer.id) == 0

    approved = client.post(
        f"{PREFIX}/approvals/{result.warranty.id}/approve",
        headers=h,
        json={"reason": "Paper invoice checked", "honour_requested_date": True},
    )
    assert approved.status_code == 200, approved.text
    assert ledger.balance(db, dealer.id) == 50


def test_rejecting_an_approval_voids_it_and_pays_nobody(client, db, h):
    from app.dealer.services.warranty_dates import business_today

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    product = make_priced_product(db, 50)
    result = registration.register(
        db,
        staff=staff,
        product_id=product.id,
        customer_phone="+919812345678",
        customer_name="Asha",
        invoice_ref="INV-1",
        invoice_date=business_today() - timedelta(days=400),
    )
    db.commit()

    resp = client.post(
        f"{PREFIX}/approvals/{result.warranty.id}/reject",
        headers=h,
        json={"reason": "No invoice produced"},
    )
    assert resp.status_code == 200, resp.text
    db.refresh(result.warranty)
    assert result.warranty.status == "voided"
    assert ledger.balance(db, dealer.id) == 0


# --- compliance, dashboard, lookup, audit ---------------------------------


def test_compliance_ranks_the_shop_customers_had_to_register_for(client, db, h):
    """Without allocations the ranking runs on what a shop DID or failed to do.

    A customer registering their own warranty is direct evidence a shop did not,
    and it needs no allocation to mean something.
    """
    from app.dealer.models.customer import Customer
    from app.dealer.models.warranty import Warranty
    from app.dealer.services.warranty_dates import business_today

    good = make_dealer(db, code="GOOD", name="Diligent Beds")
    bad = make_dealer(db, code="BAD", name="Silent Beds")
    good_staff = make_staff(db, good, phone="+919000000011")
    make_staff(db, bad, phone="+919000000012")

    product = make_priced_product(db, 50)
    for i in range(2):
        registration.register(
            db,
            staff=good_staff,
            product_id=product.id,
            customer_phone=f"+91981234{i:04d}",
            customer_name="C",
            invoice_ref=f"I{i}",
        )

    # two customers had to register their own purchases, and named this shop
    customer = Customer(phone="+919812349999", name="Self Registrant")
    db.add(customer)
    db.flush()
    for _ in range(2):
        db.add(
            Warranty(
                serial=new_serial(),
                warranty_months=60,
                dealer_id=bad.id,
                customer_id=customer.id,
                warranty_start_date=business_today(),
                warranty_end_date=business_today().replace(year=business_today().year + 5),
                status="pending_review",
                source="customer_self",
            )
        )
    db.commit()

    rows = client.get(f"{PREFIX}/compliance", headers=h).json()["items"]
    codes = [r["dealer_code"] for r in rows]
    assert codes.index("BAD") < codes.index("GOOD"), "the shop customers registered for ranks first"

    bad_row = next(r for r in rows if r["dealer_code"] == "BAD")
    assert bad_row["self_registrations"] == 2
    assert bad_row["warranties_registered"] == 0

    good_row = next(r for r in rows if r["dealer_code"] == "GOOD")
    assert good_row["warranties_registered"] == 2
    assert good_row["self_registrations"] == 0

    drill = client.get(f"{PREFIX}/compliance/dealers/{bad.id}", headers=h)
    assert drill.status_code == 200, drill.text


def test_serial_lookup_answers_everything_in_one_response(client, db, h):
    """The screen support lives on, now serving only the mattresses that have a
    serial: everything sold before the dropdown replaced the scanner.

    Those warranties run for years, so a customer reading a label off one is a
    call the desk still takes daily — and this response is what they answer it
    from. A sale registered today has no serial and is reached by invoice number
    through /warranties instead.
    """
    from tests.dealer.factories import make_unit

    dealer = make_dealer(db)
    serial = new_serial()
    make_unit(db, serial)
    make_legacy_warranty(db, dealer=dealer, serial=serial, invoice_ref="INV-OLD-1")
    db.commit()

    body = client.get(f"{PREFIX}/lookup/{serial}", headers=h).json()
    assert body["unit"]["known"] is True
    assert body["current_warranty"] is not None
    assert body["events"], "support works from the event timeline"
    assert body["warranties"], "every warranty ever on this serial, not just the live one"


def test_lookup_of_an_unknown_serial_is_an_answer_not_an_error(client, db, h):
    body = client.get(f"{PREFIX}/lookup/{new_serial()}", headers=h)
    assert body.status_code == 200
    assert body.json()["unit"]["known"] is False


def test_dashboard_and_audit_feeds(client, db, h):
    _sell(db)
    dash = client.get(f"{PREFIX}/dashboard", headers=h).json()
    assert dash["registered_today"] == 1
    an = client.get(f"{PREFIX}/dashboard/analytics?days=5", headers=h).json()
    assert len(an["series"]) == 5

    audit = client.get(f"{PREFIX}/audit", headers=h)
    assert audit.status_code == 200
    filters = client.get(f"{PREFIX}/audit/filters", headers=h).json()
    assert "actions" in filters and "entity_types" in filters
    assert client.get(f"{PREFIX}/me", headers=h).json()["role"] == "owner"


# --- rewards, redemptions, sms, points -------------------------------------


def test_reward_catalogue_and_redemption_queue(client, db, h):
    dealer, staff, _ = _sell(db, points=500)

    created = client.post(
        f"{PREFIX}/rewards", headers=h, json={"name": "Bedsheet set", "points_cost": 200}
    )
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    assert client.get(f"{PREFIX}/rewards", headers=h).json()["total"] == 1
    assert client.get(f"{PREFIX}/rewards/{rid}", headers=h).status_code == 200
    assert (
        client.patch(
            f"{PREFIX}/rewards/{rid}",
            headers=h,
            json={"name": "Bedsheet set XL", "points_cost": 250},
        ).status_code
        == 200
    )

    dealer_token = create_access_token(str(staff.id), "dealer")
    req = client.post(
        "/api/v1/dealer/redemptions",
        headers={"Authorization": f"Bearer {dealer_token}"},
        json={"reward_id": rid},
    )
    assert req.status_code in (200, 201), req.text
    red_id = req.json()["id"]

    queue = client.get(f"{PREFIX}/redemptions", headers=h).json()
    assert queue["total"] == 1

    approved = client.post(f"{PREFIX}/redemptions/{red_id}/approve", headers=h, json={})
    assert approved.status_code == 200, approved.text
    assert ledger.balance(db, dealer.id) == 250

    assert (
        client.post(f"{PREFIX}/redemptions/{red_id}/mark-fulfilled", headers=h, json={}).status_code
        == 200
    )


def test_sms_log_lists_and_retries(client, db, h):
    _sell(db)  # registration queues a warranty SMS
    # A message exists only once something queued one; the service layer used by
    # _sell does not (the router does), so queue one the way the app does.
    from app.dealer.services import sms as sms_svc

    msg = sms_svc.queue(
        db,
        phone="+919812345678",
        template_key="warranty_registered",
        variables={
            "name": "Asha",
            "model": "M",
            "end_date": "01-01-2031",
            "serial": "abc",
            "link": "http://x/w/1",
        },
    )
    db.commit()

    listed = client.get(f"{PREFIX}/sms", headers=h).json()
    assert listed["total"] >= 1
    assert client.get(f"{PREFIX}/sms/{msg.id}", headers=h).status_code == 200
    assert client.get(f"{PREFIX}/sms/templates", headers=h).status_code == 200
    retried = client.post(f"{PREFIX}/sms/{msg.id}/retry", headers=h)
    assert retried.status_code in (200, 409)


def test_point_rates_are_per_product_and_versioned(client, db, h):
    product = make_product(db, name="Priced Model")
    db.commit()

    current = client.get(f"{PREFIX}/points/rates/current", headers=h).json()
    row = next(r for r in current if r["product_id"] == str(product.id))
    assert row["points_per_registration"] is None, "an unpriced product must be visible"

    first = client.post(
        f"{PREFIX}/points/rate",
        headers=h,
        json={"product_id": str(product.id), "points_per_registration": 50, "note": "launch"},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"{PREFIX}/points/rate",
        headers=h,
        json={"product_id": str(product.id), "points_per_registration": 75, "note": "raise"},
    )
    assert second.status_code == 201

    history = client.get(f"{PREFIX}/points/rates?product_id={product.id}", headers=h).json()
    assert history["total"] == 2, "the old rate is closed, not overwritten"


def test_support_role_can_read_but_not_move_points(client, db):
    support = make_admin(db, email="support@x.test", role="support")
    dealer = make_dealer(db)
    db.commit()
    sh = _headers(support)

    assert client.get(f"{PREFIX}/warranties", headers=sh).status_code == 200
    assert client.get(f"{PREFIX}/compliance", headers=sh).status_code == 200
    blocked = client.post(
        f"{PREFIX}/dealers/{dealer.id}/points/adjust",
        headers=sh,
        json={"amount": 999, "reason": "trying it on"},
    )
    assert blocked.status_code == 403


def test_claims_queue_moves_through_its_workflow(client, db, h):
    from app.dealer.models.claim import Claim

    _, _, result = _sell(db)
    claim = Claim(
        reference="ABCD2345",
        warranty_id=result.warranty.id,
        customer_id=result.warranty.customer_id,
        description="Sagging after three months",
        status="open",
    )
    db.add(claim)
    db.commit()

    listed = client.get(f"{PREFIX}/claims", headers=h).json()
    assert listed["total"] == 1
    assert client.get(f"{PREFIX}/claims/{claim.id}", headers=h).status_code == 200
    moved = client.patch(
        f"{PREFIX}/claims/{claim.id}",
        headers=h,
        json={"status": "approved", "resolution_note": "Replacement despatched"},
    )
    assert moved.status_code == 200, moved.text


def test_an_unauthenticated_caller_gets_nothing(client):
    for path in ("/dealers", "/warranties", "/compliance", "/dashboard"):
        assert client.get(f"{PREFIX}{path}").status_code == 401


def test_the_first_dealer_admin_can_be_created_from_the_environment(
    db, session_factory, monkeypatch
):
    """Render's plan has no shell, so without this the dealer panel would deploy
    with nobody able to sign in."""
    from app.core.config import settings
    from app.core.security import verify_password
    from app.dealer.bootstrap import ensure_bootstrap_dealer_admin
    from app.dealer.models.admin import DealerAdmin

    monkeypatch.setattr(settings, "dealer_bootstrap_admin_email", "First.Owner@Goodbed.test")
    monkeypatch.setattr(settings, "dealer_bootstrap_admin_password", "a-strong-password")
    # the function opens its own session against the app's engine; point it at
    # the test database instead
    monkeypatch.setattr("app.dealer.bootstrap.SessionLocal", session_factory)

    ensure_bootstrap_dealer_admin()
    admin = db.query(DealerAdmin).filter_by(email="first.owner@goodbed.test").one()
    assert admin.role == "owner"
    assert verify_password("a-strong-password", admin.password_hash)
    assert admin.password_hash != "a-strong-password", "never store the plaintext"

    # idempotent: a redeploy must not fail or duplicate
    ensure_bootstrap_dealer_admin()
    assert db.query(DealerAdmin).filter_by(email="first.owner@goodbed.test").count() == 1


def test_bootstrap_is_a_no_op_when_unset(db, session_factory, monkeypatch):
    from app.dealer.bootstrap import ensure_bootstrap_dealer_admin
    from app.dealer.models.admin import DealerAdmin

    monkeypatch.setattr("app.dealer.bootstrap.SessionLocal", session_factory)

    before = db.query(DealerAdmin).count()
    ensure_bootstrap_dealer_admin()
    assert db.query(DealerAdmin).count() == before
