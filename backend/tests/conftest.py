from collections.abc import Iterator

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

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
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
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
def client(db: Session, redis: fakeredis.FakeRedis) -> Iterator[TestClient]:
    from app.core.deps import get_db, get_redis
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
