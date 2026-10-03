"""
Shared test fixtures.

Tests run against a throwaway SQLite database file rather than the
developer's local ecotwin.db or a real Postgres instance, so the test
suite is self-contained and repeatable (see docs/TESTING.md).
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_ecotwin.db"

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import Base, engine, init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _setup_test_database():
    get_settings.cache_clear()
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
    db_path = "./test_ecotwin.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def db_session():
    """A DB session for service-layer tests, committed per-test (SQLite
    test DB is shared across the session but each test uses unique names
    to avoid collisions)."""
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
