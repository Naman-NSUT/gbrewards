"""Dashboard aggregates and the allocation dry run."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.core.security import create_access_token
from app.dealer.models.allocation import Allocation
from app.dealer.services import registration
from app.main import create_app
from tests.dealer.factories import (
    allocate,
    make_admin,
    make_dealer,
    make_priced_unit,
    make_staff,
    make_unit,
    new_serial,
)


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    def _get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_headers(db):  # type: ignore[no-untyped-def]
    admin = make_admin(db)
    db.commit()
    token = create_access_token(str(admin.id), "dealer_admin", {"role": admin.role})
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_separates_dealer_and_customer_registrations(client, db, admin_headers):
    """Folding self-registrations into the headline total would hide the exact
    problem this product exists to expose."""
    from app.dealer.models.customer import Customer
    from app.dealer.models.warranty import Warranty
    from app.dealer.services.warranty_dates import business_today

    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    serial = new_serial()
    make_priced_unit(db, serial, 50)
    allocate(db, serial, dealer)
    registration.register(
        db,
        staff=staff,
        raw_serial=serial,
        customer_phone="+919812345678",
        customer_name="Asha",
        invoice_ref="INV-1",
    )

    # A customer who had to register their own purchase.
    customer = Customer(phone="+919812349999", name="Self Registrant")
    db.add(customer)
    db.flush()
    db.add(
        Warranty(
            serial=new_serial(),
            warranty_months=60,
            dealer_id=dealer.id,
            customer_id=customer.id,
            warranty_start_date=business_today(),
            warranty_end_date=business_today().replace(year=business_today().year + 5),
            status="pending_review",
            source="customer_self",
        )
    )
    db.commit()

    body = client.get("/api/v1/dealer-admin/dashboard", headers=admin_headers).json()

    assert body["registered_today"] == 1
    assert body["self_registered_this_month"] == 1
    assert body["pending_approvals"] == 1
    assert body["active_dealers"] == 1
    assert body["points_issued"] == 50


def test_analytics_returns_a_dense_series_with_no_gaps(client, db, admin_headers):
    """A chart with missing days renders a misleading line."""
    body = client.get(
        "/api/v1/dealer-admin/dashboard/analytics?days=7", headers=admin_headers
    ).json()
    assert body["days"] == 7
    assert len(body["series"]) == 7
    assert all({"date", "dealer", "customer_self"} <= set(p) for p in body["series"])
    dates = [p["date"] for p in body["series"]]
    assert dates == sorted(dates)


def test_allocation_preview_writes_nothing_but_reports_what_upload_would_do(
    client, db, admin_headers
):
    make_dealer(db, code="D001")
    serial = new_serial()
    make_unit(db, serial)          # a real manufactured unit
    bad_dealer_serial = new_serial()
    make_unit(db, bad_dealer_serial)
    db.commit()
    # Second row names a dealer that does not exist, so it is rejected for that
    # reason rather than for a missing unit.
    csv = (
        f"serial,dealer_code\n{serial},D001\n{bad_dealer_serial},NOPE\n"
    ).encode()

    preview = client.post(
        "/api/v1/dealer-admin/allocations/preview",
        headers=admin_headers,
        files={"file": ("despatch.csv", csv, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert p["created_count"] == 1
    assert len(p["errors"]) == 1

    assert db.query(Allocation).count() == 0, "a dry run must write nothing"
    from app.dealer.models.allocation import AllocationBatch

    assert db.query(AllocationBatch).count() == 0, "not even the batch row"

    # The real upload must agree with what the preview promised.
    upload = client.post(
        "/api/v1/dealer-admin/allocations/upload",
        headers=admin_headers,
        files={"file": ("despatch.csv", csv, "text/csv")},
    )
    assert upload.status_code in (200, 201), upload.text
    u = upload.json()
    assert u["created_count"] == p["created_count"]
    assert len(u["errors"]) == len(p["errors"])
    assert db.query(Allocation).count() == 1


def test_dealer_token_cannot_reach_the_admin_dashboard(client, db):
    dealer = make_dealer(db)
    staff = make_staff(db, dealer)
    db.commit()
    token = create_access_token(str(staff.id), "dealer")
    resp = client.get(
        "/api/v1/dealer-admin/dashboard", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


def test_support_role_cannot_move_points(client, db):
    """Support staff work lookup and claims all day; they must not adjust balances."""
    from app.dealer.models.admin import DealerAdmin as Admin

    support = Admin(
        email="support@goodbed.test", password_hash="x", name="Support", role="support"
    )
    dealer = make_dealer(db)
    db.add(support)
    db.commit()
    token = create_access_token(str(support.id), "dealer_admin", {"role": "support"})

    resp = client.post(
        f"/api/v1/dealer-admin/dealers/{dealer.id}/points/adjust",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 500, "reason": "because I can"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_manual_adjustment_without_a_reason_is_refused(client, db, admin_headers):
    dealer = make_dealer(db)
    db.commit()
    resp = client.post(
        f"/api/v1/dealer-admin/dealers/{dealer.id}/points/adjust",
        headers=admin_headers,
        json={"amount": 500, "reason": "   "},
    )
    assert resp.status_code in (400, 422)
    assert str(uuid.UUID(str(dealer.id)))  # sanity: the dealer id round-trips


def test_daily_counts_use_the_sellers_calendar_day_not_utc(client, db, admin_headers, monkeypatch):
    """A sale at 01:30 IST belongs to that IST day, not to the previous UTC one.

    This is pinned deterministically because the bug it guards against is only
    observable between 00:00 and 05:30 IST (18:30-24:00 UTC) — a five-and-a-half
    hour window that a test running at any other time would sail straight past.
    Truncating registered_at with date() truncates in UTC, so the dashboard used
    to report yesterday's figure for the first five and a half hours of every day.
    """
    from datetime import UTC, date, datetime

    from app.dealer.api.admin import dashboard as dashboard_module
    from app.dealer.models.customer import Customer
    from app.dealer.models.warranty import Warranty

    ist_day = date(2026, 8, 20)
    # 19:30 UTC on the 19th == 01:00 IST on the 20th.
    sold_at = datetime(2026, 8, 19, 19, 30, tzinfo=UTC)

    monkeypatch.setattr(dashboard_module, "business_today", lambda: ist_day)

    dealer = make_dealer(db)
    customer = Customer(phone="+919812345678", name="Night Owl")
    db.add(customer)
    db.flush()
    db.add(
        Warranty(
            serial=new_serial(),
            warranty_months=60,
            dealer_id=dealer.id,
            customer_id=customer.id,
            warranty_start_date=ist_day,
            warranty_end_date=date(2031, 8, 20),
            status="active",
            source="dealer",
            registered_at=sold_at,
        )
    )
    db.commit()

    body = client.get("/api/v1/dealer-admin/dashboard", headers=admin_headers).json()
    assert body["registered_today"] == 1, (
        "a 01:00 IST sale must count toward the IST day it happened on"
    )
    assert body["registered_this_month"] == 1
