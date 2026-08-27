"""Boot-time resilience: the API must come up even when Postgres will not.

Render starts this container independently of the managed Postgres and probes
/api/v1/healthz. Anything fatal that runs before uvicorn binds a port turns a
database blip lasting seconds into a crash loop that outlives it, so these tests
pin the two boot paths that used to be fatal, plus the readiness endpoint that
is deliberately allowed to fail.
"""

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.deps import get_db, get_redis
from app.db.bootstrap import ensure_bootstrap_admin
from app.dealer.models.admin import DealerAdmin
from app.main import create_app
from app.models.admin import Admin

BOOTSTRAP_ADMIN_EMAIL = "boot-admin@example.com"
BOOTSTRAP_DEALER_ADMIN_EMAIL = "boot-dealer-admin@example.com"


def _connection_refused() -> Session:
    """Stand-in for SessionLocal while Postgres is refusing connections."""
    raise OperationalError(
        "SELECT 1",
        {},
        Exception("connection to server failed: Connection refused"),
    )


def _configure_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set both credential pairs.

    Both ensure_* functions return early when their env vars are unset, so an
    unconfigured deploy never touches the database at boot and never saw this
    bug. Only the deploy that actually wants a first account does — i.e. exactly
    the deploy the feature exists for.
    """
    monkeypatch.setattr(settings, "bootstrap_admin_email", BOOTSTRAP_ADMIN_EMAIL)
    monkeypatch.setattr(settings, "bootstrap_admin_password", "boot-admin-pw")
    monkeypatch.setattr(settings, "dealer_bootstrap_admin_email", BOOTSTRAP_DEALER_ADMIN_EMAIL)
    monkeypatch.setattr(settings, "dealer_bootstrap_admin_password", "boot-dealer-pw")


def _disable_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "bootstrap_admin_email", "")
    monkeypatch.setattr(settings, "bootstrap_admin_password", "")
    monkeypatch.setattr(settings, "dealer_bootstrap_admin_email", "")
    monkeypatch.setattr(settings, "dealer_bootstrap_admin_password", "")


def test_app_boots_and_serves_healthz_when_the_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A database blip must not stop the process from binding a port.

    Bootstrap used to run inline in create_app(), i.e. at import, so an
    unreachable database killed the process before uvicorn could serve
    anything — and Render's health check then restarted it into the same
    failure until the blip was long over.
    """
    _configure_bootstrap(monkeypatch)
    monkeypatch.setattr("app.db.bootstrap.SessionLocal", _connection_refused)
    monkeypatch.setattr("app.dealer.bootstrap.SessionLocal", _connection_refused)

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_bootstrap_admin_survives_another_instance_winning_the_race(
    db_truncate: "sessionmaker[Session]", monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two instances off one deploy both find no admin; the loser must not die.

    Both SELECT an empty admins table, both INSERT, and uq_admins_email rejects
    the second. The row exists either way, so the loser's only job is to stop
    treating that as a reason to abort its own startup.
    """
    monkeypatch.setattr(settings, "bootstrap_admin_email", BOOTSTRAP_ADMIN_EMAIL)
    monkeypatch.setattr(settings, "bootstrap_admin_password", "boot-admin-pw")
    monkeypatch.setattr("app.db.bootstrap.SessionLocal", db_truncate)

    def _other_instance_commits_first(secret: str) -> str:
        # hash_secret is evaluated between this instance's SELECT (which found
        # nothing) and its INSERT, so committing from a second connection here
        # reproduces the real window rather than simulating it.
        with db_truncate() as other:
            other.add(
                Admin(
                    email=BOOTSTRAP_ADMIN_EMAIL,
                    password_hash="hash-from-the-other-instance",
                    role="owner",
                )
            )
            other.commit()
        return "hash-from-this-instance"

    monkeypatch.setattr("app.db.bootstrap.hash_secret", _other_instance_commits_first)

    ensure_bootstrap_admin()

    with db_truncate() as check:
        admins = check.query(Admin).filter(Admin.email == BOOTSTRAP_ADMIN_EMAIL).all()
    assert len(admins) == 1
    assert admins[0].password_hash == "hash-from-the-other-instance"


def test_readyz_fails_closed_when_the_database_is_down(
    redis: fakeredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Characterisation guard: /readyz reports 500, never a 200 'degraded'.

    Readiness exists to take an instance out of rotation. A 200 carrying a
    warning field would keep routing dealer traffic at a process that cannot
    read a warranty, so this stays fail-closed. healthz — the path render.yaml
    actually probes — touches no database and must stay up regardless.
    """
    _disable_bootstrap(monkeypatch)

    def _db_down() -> Session:
        raise OperationalError("SELECT 1", {}, Exception("Connection refused"))

    app = create_app()
    app.dependency_overrides[get_db] = _db_down
    app.dependency_overrides[get_redis] = lambda: redis
    # The catch-all handler builds the 500 and then re-raises, so the client has
    # to be told to report the response rather than the exception.
    with TestClient(app, raise_server_exceptions=False) as client:
        ready = client.get("/api/v1/readyz")
        healthz = client.get("/api/v1/healthz")
    app.dependency_overrides.clear()

    assert ready.status_code == 500
    assert ready.json()["error"]["code"] == "internal_error"
    assert "status" not in ready.json()
    assert healthz.status_code == 200


def test_healthy_boot_still_creates_both_first_accounts(
    db_truncate: "sessionmaker[Session]", monkeypatch: pytest.MonkeyPatch
) -> None:
    """Making bootstrap non-fatal must not quietly make it optional.

    Render's plan has no shell: if these two accounts are not created at boot,
    nobody can sign into either back office at all.
    """
    _configure_bootstrap(monkeypatch)
    monkeypatch.setattr("app.db.bootstrap.SessionLocal", db_truncate)
    monkeypatch.setattr("app.dealer.bootstrap.SessionLocal", db_truncate)

    app = create_app()
    with TestClient(app):
        pass

    with db_truncate() as check:
        admin = check.query(Admin).filter(Admin.email == BOOTSTRAP_ADMIN_EMAIL).one_or_none()
        dealer_admin = (
            check.query(DealerAdmin)
            .filter(DealerAdmin.email == BOOTSTRAP_DEALER_ADMIN_EMAIL)
            .one_or_none()
        )
    assert admin is not None
    assert admin.role == "owner"
    assert dealer_admin is not None
    assert dealer_admin.role == "owner"
