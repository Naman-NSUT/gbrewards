"""Both back-office logins must hash a password even when the email is unknown.

The leak these guard against is a timing side channel, not a wrong answer: both
endpoints return the same 401 either way, but the *cost* of that 401 used to give
the game away. `admin is None or not verify_*(...)` never reaches the verify when
the row is missing, so an unregistered address answered in about a millisecond
while a real one paid argon2's deliberate ~50-100ms. Anyone could time the 401 and
read off which addresses belong to the client's back-office staff.

Deliberately NOT a wall-clock assertion — those are flaky on shared CI. What is
asserted is the mechanism: the verify function actually runs on the miss path, and
it runs against the module's import-time dummy hash, which is the only way the two
paths can cost the same.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.v1.admin.auth as worker_admin_auth
import app.dealer.api.dealer.auth as dealer_admin_auth
from app.core.security import hash_password
from app.dealer.models.admin import DealerAdmin
from tests.factories import make_admin

WORKER_LOGIN = "/api/v1/admin/auth/login"
DEALER_LOGIN = "/api/v1/dealer/auth/admin/login"


@pytest.fixture
def worker_verify_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Record every verify_secret(hash, password) the worker login performs."""
    calls: list[tuple[str, str]] = []
    real = worker_admin_auth.verify_secret

    def spy(hashed: str, secret: str) -> bool:
        calls.append((hashed, secret))
        return real(hashed, secret)

    monkeypatch.setattr(worker_admin_auth, "verify_secret", spy)
    return calls


@pytest.fixture
def dealer_verify_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Record every verify_password(password, hash) the dealer login performs.

    Note the argument order is the mirror of the worker module's helper; the two
    programmes grew their own names for the same argon2 call.
    """
    calls: list[tuple[str, str]] = []
    real = dealer_admin_auth.verify_password

    def spy(password: str, password_hash: str) -> bool:
        calls.append((password, password_hash))
        return real(password, password_hash)

    monkeypatch.setattr(dealer_admin_auth, "verify_password", spy)
    return calls


def test_worker_login_hashes_for_unknown_email(
    client: TestClient, worker_verify_calls: list[tuple[str, str]]
) -> None:
    r = client.post(
        WORKER_LOGIN,
        json={"email": "not-an-admin@example.com", "password": "guess-me"},
    )

    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"
    # The point of the fix: argon2 ran, against the dummy, on the miss path.
    assert worker_verify_calls == [(worker_admin_auth._DUMMY_PASSWORD_HASH, "guess-me")]


def test_worker_login_hashes_the_same_way_for_a_known_email(
    client: TestClient, db: Session, worker_verify_calls: list[tuple[str, str]]
) -> None:
    """The equaliser must not have changed what a real login verifies against."""
    admin = make_admin(db, email="boss@example.com", password="s3cret123")
    db.commit()

    r = client.post(
        WORKER_LOGIN,
        json={"email": "boss@example.com", "password": "wrong-pass"},
    )

    assert r.status_code == 401
    assert worker_verify_calls == [(admin.password_hash, "wrong-pass")]
    assert admin.password_hash != worker_admin_auth._DUMMY_PASSWORD_HASH


def test_dealer_admin_login_hashes_for_unknown_email(
    client: TestClient, dealer_verify_calls: list[tuple[str, str]]
) -> None:
    r = client.post(
        DEALER_LOGIN,
        json={"email": "nobody@example.com", "password": "guess-me"},
    )

    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"
    assert dealer_verify_calls == [("guess-me", dealer_admin_auth._DUMMY_PASSWORD_HASH)]


def test_dealer_admin_login_hashes_the_same_way_for_a_known_email(
    client: TestClient, db: Session, dealer_verify_calls: list[tuple[str, str]]
) -> None:
    admin = DealerAdmin(
        email="owner@example.com",
        password_hash=hash_password("s3cret123"),
        name="Owner",
        role="owner",
    )
    db.add(admin)
    db.commit()

    r = client.post(
        DEALER_LOGIN,
        json={"email": "owner@example.com", "password": "wrong-pass"},
    )

    assert r.status_code == 401
    assert dealer_verify_calls == [("wrong-pass", admin.password_hash)]
    assert admin.password_hash != dealer_admin_auth._DUMMY_PASSWORD_HASH


def test_dealer_admin_login_normalises_before_deciding_which_hash_to_use(
    client: TestClient, db: Session, dealer_verify_calls: list[tuple[str, str]]
) -> None:
    """A shouted email is the same account, so it must take the real-hash path.

    Guards the ordering: the lower/strip has to happen before the row lookup that
    chooses between the real hash and the dummy, or every operator who types their
    address with a capital letter silently lands on the equaliser and can never
    sign in.
    """
    admin = DealerAdmin(
        email="owner@example.com",
        password_hash=hash_password("s3cret123"),
        name="Owner",
        role="owner",
    )
    db.add(admin)
    db.commit()

    r = client.post(
        DEALER_LOGIN,
        json={"email": "  Owner@Example.com  ", "password": "s3cret123"},
    )

    assert r.status_code == 200, r.text
    assert dealer_verify_calls == [("s3cret123", admin.password_hash)]


def test_dummy_hash_is_reused_across_misses(
    client: TestClient,
    worker_verify_calls: list[tuple[str, str]],
    dealer_verify_calls: list[tuple[str, str]],
) -> None:
    """Two misses must verify against the one hash built at import.

    Minting a fresh throwaway per request would put a measurable gap back — argon2
    hashing costs more than verifying, so unknown emails would become the *slow*
    ones and the endpoint would still answer "does this person work here?", just
    with the sign flipped.
    """
    for email in ("ghost-one@example.com", "ghost-two@example.com"):
        assert client.post(WORKER_LOGIN, json={"email": email, "password": "x"}).status_code == 401
        assert client.post(DEALER_LOGIN, json={"email": email, "password": "x"}).status_code == 401

    worker_hashes = {hashed for hashed, _ in worker_verify_calls}
    dealer_hashes = {password_hash for _, password_hash in dealer_verify_calls}
    assert worker_hashes == {worker_admin_auth._DUMMY_PASSWORD_HASH}
    assert dealer_hashes == {dealer_admin_auth._DUMMY_PASSWORD_HASH}
    # Real argon2 output, not a placeholder that would verify in microseconds.
    assert worker_admin_auth._DUMMY_PASSWORD_HASH.startswith("$argon2")
    assert dealer_admin_auth._DUMMY_PASSWORD_HASH.startswith("$argon2")
