"""Dealer self-signup.

Shops create their own accounts. The property these tests exist to protect is
that NOTHING is written until the phone is proven — the neighbouring worker
programme creates or updates its user row on the OTP *request*, which lets anyone
who knows a registered number overwrite that user's profile unauthenticated.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.dealer.models.dealer import Dealer, DealerStaff
from app.dealer.models.sms_message import SmsMessage
from app.main import create_app

AUTH = "/api/v1/dealer/auth"


@pytest.fixture
def client(db, session_factory):  # type: ignore[no-untyped-def]
    app = create_app()

    def _get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    import fakeredis

    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fake
    with TestClient(app) as c:
        c.fake_redis = fake  # type: ignore[attr-defined]
        yield c


def _signup(client, phone="9812300001", shop="Sunrise Beds"):
    return client.post(
        f"{AUTH}/signup",
        json={
            "phone": phone,
            "name": "Ravi Mehta",
            "shop_name": shop,
            "city": "Nagpur",
            "gst_number": "27AAAAA0000A1Z5",
        },
    )


def _latest_otp(db) -> str:
    msg = (
        db.query(SmsMessage)
        .filter_by(template_key="login_otp")
        .order_by(SmsMessage.created_at.desc())
        .first()
    )
    assert msg is not None, "signup must send a code"
    return str(msg.variables["otp"])


def test_signup_writes_nothing_until_the_phone_is_proven(client, db):
    """The whole point of staging. A shop that types its details and walks away
    must leave no dealership behind, and no half-made account for someone else
    to inherit."""
    resp = _signup(client)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_new_account"] is True

    assert db.query(Dealer).count() == 0, "no dealership before the code is verified"
    assert db.query(DealerStaff).count() == 0, "and no staff either"


def test_verifying_the_code_creates_the_shop_and_signs_them_in(client, db):
    _signup(client)
    code = _latest_otp(db)

    resp = client.post(f"{AUTH}/otp/verify", json={"phone": "9812300001", "code": code})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["dealer"]["name"] == "Sunrise Beds"
    assert body["staff"]["role"] == "owner", "whoever signs the shop up owns it"

    dealer = db.query(Dealer).one()
    assert dealer.status == "pending", "a new shop is not trusted with payouts yet"
    assert dealer.gst_number == "27AAAAA0000A1Z5"
    assert dealer.code.startswith("D"), "a short code staff can quote down the phone"
    assert db.query(DealerStaff).one().phone == "+919812300001"


def test_a_pending_shop_can_register_sales_immediately(client, db):
    """Capturing the sale record is the product. It must not wait on an admin."""
    import uuid as _uuid

    from tests.dealer.factories import make_priced_product

    _signup(client)
    token = client.post(
        f"{AUTH}/otp/verify", json={"phone": "9812300001", "code": _latest_otp(db)}
    ).json()["access_token"]

    product = make_priced_product(db, 50)
    db.commit()

    resp = client.post(
        "/api/v1/dealer/registrations",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(_uuid.uuid4())},
        json={
            "product_id": str(product.id),
            "customer_phone": "9876500001",
            "customer_name": "Meera",
            "invoice_ref": "INV-1",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["points_awarded"] == 50, "points accrue while pending"


def test_a_pending_shop_cannot_redeem_until_it_is_approved(client, db):
    """Points accrue; money does not leave until a human has looked once."""
    from app.dealer.models.reward import Reward

    _signup(client)
    token = client.post(
        f"{AUTH}/otp/verify", json={"phone": "9812300001", "code": _latest_otp(db)}
    ).json()["access_token"]

    reward = Reward(name="Bedsheet", points_cost=10)
    db.add(reward)
    db.commit()

    resp = client.post(
        "/api/v1/dealer/redemptions",
        headers={"Authorization": f"Bearer {token}"},
        json={"reward_id": str(reward.id)},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "dealer_pending_approval"
    # and the message tells them their points are safe, not that they failed
    assert "points are safe" in resp.json()["error"]["message"]


def test_signing_up_a_number_that_already_has_an_account_is_refused(client, db):
    _signup(client)
    client.post(f"{AUTH}/otp/verify", json={"phone": "9812300001", "code": _latest_otp(db)})

    resp = _signup(client, shop="Second Shop")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "already_registered"
    assert db.query(Dealer).count() == 1


def test_verifying_with_no_signup_and_no_account_is_refused(client, db):
    from app.dealer.services import otp as otp_svc

    otp_svc.issue(db, client.fake_redis, "+919812300009")
    db.commit()
    resp = client.post(f"{AUTH}/otp/verify", json={"phone": "9812300009", "code": _latest_otp(db)})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "account_not_found"
    assert db.query(Dealer).count() == 0


def test_each_shop_gets_its_own_code(client, db):
    for i, shop in enumerate(("Alpha Beds", "Beta Beds")):
        phone = f"98123000{10 + i}"
        _signup(client, phone=phone, shop=shop)
        client.post(f"{AUTH}/otp/verify", json={"phone": phone, "code": _latest_otp(db)})
    codes = {d.code for d in db.query(Dealer).all()}
    assert len(codes) == 2, f"codes must be unique, got {codes}"


def test_auto_approve_skips_the_pending_state(client, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "dealer_signup_auto_approve", True)
    _signup(client)
    client.post(f"{AUTH}/otp/verify", json={"phone": "9812300001", "code": _latest_otp(db)})
    assert db.query(Dealer).one().status == "active"


def test_signing_in_with_an_unknown_number_says_so(client, db):
    """The bug this fixes: a dealer tapped sign in, got a cheerful 'code sent',
    and waited forever for a code that was never generated.

    Disclosing that no account exists is safe now — anyone can learn the same
    thing by attempting a signup and reading `already_registered` — and the
    silence was a dead end.
    """
    from app.dealer.models.sms_message import SmsMessage

    resp = client.post(f"{AUTH}/otp/request", json={"phone": "9812309999"})
    assert resp.status_code == 200
    assert resp.json()["account_exists"] is False
    assert db.query(SmsMessage).count() == 0, "no code should be generated"


def test_signing_in_with_a_known_number_sends_a_code(client, db):
    from app.dealer.models.sms_message import SmsMessage

    _signup(client)
    client.post(f"{AUTH}/otp/verify", json={"phone": "9812300001", "code": _latest_otp(db)})
    before = db.query(SmsMessage).count()

    # The signup moments ago left a resend cooldown; clear it rather than
    # sleeping through a real 30 seconds.
    client.fake_redis.delete("otp:cooldown:+919812300001")

    resp = client.post(f"{AUTH}/otp/request", json={"phone": "9812300001"})
    assert resp.status_code == 200
    assert resp.json()["account_exists"] is True
    assert db.query(SmsMessage).count() == before + 1


def test_twofactor_sends_the_login_code_but_refuses_a_warranty_message(monkeypatch):
    """The login code and the worker OTP are the same shape, so the existing
    approved template carries it. A warranty message is not, and must fail
    loudly rather than vanish."""
    import httpx

    from app.core.config import settings
    from app.dealer.services import sms as sms_svc

    monkeypatch.setattr(settings, "twofactor_api_key", "test-key")
    monkeypatch.setattr(settings, "twofactor_template_name", "OTP1")
    sent: dict[str, str] = {}

    class _Resp:
        is_error = False
        text = '{"Status":"Success","Details":"abc-123"}'

        @staticmethod
        def json() -> dict[str, str]:
            return {"Status": "Success", "Details": "abc-123"}

    def _get(url: str, **_: object) -> _Resp:
        sent["url"] = url
        return _Resp()

    monkeypatch.setattr(httpx, "get", _get)
    provider = sms_svc.TwoFactorProvider()

    ref = provider.send("+919812300001", sms_svc.TEMPLATES["login_otp"], {"otp": "123456"})
    assert ref == "abc-123"
    assert "/SMS/919812300001/123456/OTP1" in sent["url"], "no '+' and the approved template"

    with pytest.raises(RuntimeError, match="multi-variable"):
        provider.send(
            "+919812300001",
            sms_svc.TEMPLATES["warranty_registered"],
            {"name": "Asha", "model": "M", "end_date": "01-01-2031", "serial": "s", "link": "l"},
        )
