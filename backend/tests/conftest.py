import os
import pathlib
import subprocess
from collections.abc import Iterator
from typing import TYPE_CHECKING

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

if TYPE_CHECKING:
    from app.services.otp_provider import FakeOtpProvider

# Derive a dedicated test database URL from the configured one.
_base_url = make_url(settings.database_url)
TEST_DB_NAME = f"{_base_url.database}_test"
TEST_DB_URL = _base_url.set(database=TEST_DB_NAME)


def _ensure_test_database() -> None:
    admin_url = _base_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": TEST_DB_NAME},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    _ensure_test_database()
    # Wide pool: the concurrency test holds ~20 connections at once (threads block
    # on the same row lock).
    eng = create_engine(TEST_DB_URL, future=True, pool_size=30, max_overflow=10)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.commit()
    # Build the schema with ALEMBIC, not create_all.
    #
    # create_all only knows what the SQLAlchemy models declare. The guarantees
    # the dealer side depends on — partial unique indexes (one live warranty per
    # serial, one credit per warranty, one current rate per product) and the
    # append-only triggers on the ledger — exist only in the migrations. Under
    # create_all a test asserting "the database rejects this" would pass because
    # nothing rejected anything, which is the worst possible kind of green.
    # Drop the whole schema rather than metadata.drop_all: the migrations also
    # create triggers and a plpgsql function, which metadata knows nothing about
    # and which make drop_all's ordering fail on the second run.
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        check=True,
        cwd=str(pathlib.Path(__file__).resolve().parent.parent),
        env={**os.environ, "DATABASE_URL": TEST_DB_URL.render_as_string(hide_password=False)},
        capture_output=True,
    )
    # Migrations bring schema AND their seed data (0005 inserts a default
    # banner). Tests assert against an empty database, so clear the rows while
    # keeping the schema the migrations just built.
    with eng.begin() as conn:
        names = ",".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Transactional, rolled back after each test (fast isolation)."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def db_truncate(engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Real-commit session factory for cross-connection tests (concurrency).

    Truncates all tables afterward instead of rolling back, so committed rows
    from other threads/connections are visible during the test.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    tables = ",".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def fake_otp() -> "FakeOtpProvider":
    from app.services.otp_provider import FakeOtpProvider

    return FakeOtpProvider()


@pytest.fixture
def client(
    db: Session, redis: fakeredis.FakeRedis, fake_otp: "FakeOtpProvider"
) -> Iterator[TestClient]:
    from app.core.deps import get_db, get_redis
    from app.main import app
    from app.services.otp_provider import get_otp_provider

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_otp_provider] = lambda: fake_otp
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
