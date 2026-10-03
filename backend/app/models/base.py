"""
Shared model helpers.

`GUID` is a database-portable UUID column type: it uses PostgreSQL's native
UUID type in production and falls back to a 36-character string on SQLite
(used for local dev/tests) — see docs/TECH_STACK.md and
docs/ARCHITECTURE.md for why both engines are supported.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CHAR, DateTime, Enum as SAEnum, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type when available, otherwise stores as a
    36-character hex string (e.g. on SQLite).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def utcnow() -> datetime:
    """Timezone-aware current UTC time, used for default timestamp columns."""
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column, generated client-side by default."""

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds a created_at column defaulting to the current UTC time."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def str_enum(enum_cls, **kwargs):
    """
    A SQLAlchemy Enum column that stores each member's `.value` (e.g.
    "electricity") rather than SQLAlchemy's default of the member `.name`
    (e.g. "ELECTRICITY").

    All of EcoTwin's enums are lowercase-value string enums to match
    docs/DATA_MODEL.md exactly (e.g. `resource_type` = "electricity" |
    "water", `severity` = "low" | "medium" | "high" | "critical"). Without
    `values_callable`, SQLAlchemy's Enum type persists the Python member
    name instead, which would silently diverge from the documented schema
    and from what the API returns. `native_enum=False` stores it as a
    plain VARCHAR with a CHECK constraint, which is portable between
    SQLite (local/dev) and PostgreSQL (production) without needing to
    create/alter a native Postgres enum type — one less migration concern
    for the MVP (docs/TECH_STACK.md, "avoid unnecessary complexity").
    """
    return mapped_column(
        SAEnum(enum_cls, values_callable=lambda e: [member.value for member in e], native_enum=False),
        **kwargs,
    )
