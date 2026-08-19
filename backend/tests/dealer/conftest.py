"""Dealer test fixtures layered on the shared engine in tests/conftest.py."""

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _wipe(engine: Engine) -> None:
    # TRUNCATE, not DELETE: the append-only triggers block DELETE by design, and
    # TRUNCATE does not fire row-level triggers.
    names = ",".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(engine: Engine, session_factory: sessionmaker) -> Iterator[Session]:
    """Real-commit session. Dealer tests assert on committed cross-connection
    state (idempotency reservations, concurrency), so the transactional-rollback
    fixture the worker suite uses would hide exactly what they check."""
    _wipe(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        # Wipe on the way OUT as well. These tests really commit, so anything
        # left behind is visible to the worker suite's transactional tests —
        # which count rows and would fail on our leftovers.
        _wipe(engine)


@pytest.fixture
def session_maker(
    engine: Engine, session_factory: sessionmaker
) -> Iterator[sessionmaker]:
    _wipe(engine)
    yield session_factory
    _wipe(engine)
