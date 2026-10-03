"""
Database engine and session management.

Supports both PostgreSQL (production, per docs/TECH_STACK.md and
docs/DEPLOYMENT.md) and SQLite (used for local development and automated
tests when a Postgres server isn't available). The rest of the application
only ever imports `get_db` / `SessionLocal` / `Base` from here and never
needs to know which database engine is actually in use.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create all tables that don't exist yet.

    For the MVP we use SQLAlchemy's `create_all` rather than Alembic
    migrations (see docs/ARCHITECTURE.md) — this keeps Milestone 1 simple.
    A migration tool can be introduced later (docs/FUTURE_SCOPE.md) if the
    schema needs versioned, production-safe migrations beyond hackathon
    scope.
    """
    # Import models so they are registered on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def db_healthy() -> bool:
    """Lightweight check used by the /api/health endpoint."""
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
