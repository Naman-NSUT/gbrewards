"""A shop that signed itself up must be able to keep working while it waits.

Self-signup lands a dealership in 'pending'. Sign-in and get_current_staff both
accept that on purpose — the warranty record is the product, and a customer at
the counter cannot wait on a back-office approval. Token refresh disagreed and
demanded 'active', so a pending shop signed in fine and was thrown out an hour
later when its access token expired (jwt_access_ttl_minutes is 60), with nothing
in the admin panel able to approve it.

What approval really gates is redemption, asserted here too so that "pending can
keep working" is never quietly widened into "pending can spend".
"""

import uuid

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db, get_redis
from app.core.errors import AppError
from app.core.security import create_refresh_token
from app.dealer.services import redemption
from app.main import create_app
from tests.dealer.factories import make_dealer, make_staff

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

    fake = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_redis] = lambda: fake
    with TestClient(app) as c:
        yield c


def _refresh(client, staff):  # type: ignore[no-untyped-def]
    token, _jti = create_refresh_token(str(staff.id), "dealer")
    return client.post(f"{AUTH}/refresh", json={"refresh_token": token})


def test_a_pending_shop_can_refresh_its_session(client, db):
    """The regression: an hour after signing up, a pending shop was logged out.

    Refusing the refresh sent a shop that had done nothing wrong back through
    the OTP flow every hour, mid-trading, for as long as approval took.
    """
    dealer = make_dealer(db)
    dealer.status = "pending"
    staff = make_staff(db, dealer)
    db.commit()

    resp = _refresh(client, staff)

    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_an_active_shop_can_still_refresh(client, db):
    dealer = make_dealer(db)
    dealer.status = "active"
    staff = make_staff(db, dealer)
    db.commit()

    assert _refresh(client, staff).status_code == 200


@pytest.mark.parametrize("status", ["suspended", "closed"])
def test_a_suspended_or_closed_shop_cannot_refresh(client, db, status):
    """Widening the rule must not have widened it to everyone."""
    dealer = make_dealer(db)
    dealer.status = status
    staff = make_staff(db, dealer)
    db.commit()

    resp = _refresh(client, staff)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "dealer_inactive"


def test_the_sign_in_paths_share_one_rule():
    """They drifted apart once and cost a pending shop its session every hour."""
    import inspect

    from app.core import deps
    from app.dealer.api.dealer import auth
    from app.dealer.models.dealer import SIGNED_IN_STATUSES

    assert SIGNED_IN_STATUSES == ("active", "pending")
    # No path may re-spell the tuple inline; that is exactly how they diverged.
    for module in (deps, auth):
        assert '("active", "pending")' not in inspect.getsource(module), (
            f"{module.__name__} spells the status rule out again instead of "
            "importing SIGNED_IN_STATUSES"
        )


def test_a_pending_shop_still_cannot_redeem(client, db):
    """Approval has to keep meaning something: it gates money leaving."""
    dealer = make_dealer(db)
    dealer.status = "pending"
    staff = make_staff(db, dealer)
    db.commit()

    with pytest.raises(AppError) as excinfo:
        redemption.create(db, staff=staff, reward_id=uuid.uuid4())
    assert excinfo.value.status_code == 403
