"""
PostgreSQL-compatibility regression tests (Checkpoint 9).

SQLite does not enforce `VARCHAR(n)` length limits; PostgreSQL does. That
mismatch hid a real bug until this checkpoint's real-Postgres run:
`EmissionFactor.unit` was declared `String(32)` but the seeded water
factor's unit ("kg CO2e / L (embedded/indirect energy estimate)", 47
characters) exceeds that — SQLite accepted it silently, PostgreSQL
rejected the insert outright, which would have broken the very first demo
run on a real deployment. Found and fixed by actually installing
PostgreSQL and running the full demo workflow and test suite against it,
not by inspection alone.

These tests catch that whole class of bug without needing a running
Postgres in the test environment: they check every string value this
application ever seeds against its column's declared length directly.
"""
from sqlalchemy import String

from app.core.database import Base
from app.models import CostFactor, EmissionFactor
from app.services.factor_service import DEFAULT_EMISSION_FACTORS


def _column_length(model, column_name: str) -> int | None:
    column_type = model.__table__.columns[column_name].type
    return getattr(column_type, "length", None)


def test_seeded_emission_factor_strings_fit_their_declared_column_lengths():
    for resource_type, spec in DEFAULT_EMISSION_FACTORS.items():
        for field in ("unit", "source"):
            max_length = _column_length(EmissionFactor, field)
            assert max_length is not None, f"EmissionFactor.{field} has no declared length"
            actual_length = len(spec[field])
            assert actual_length <= max_length, (
                f"Seeded {resource_type.value} EmissionFactor.{field} is {actual_length} chars but the column is "
                f"VARCHAR({max_length}) — SQLite would silently accept this; PostgreSQL rejects it."
            )


def test_seeded_cost_factor_currency_fits_its_declared_column_length():
    max_length = _column_length(CostFactor, "currency")
    assert max_length is not None
    assert len("INR") <= max_length


def test_every_string_column_in_the_schema_has_an_explicit_length():
    """A String column with no explicit length is a different portability
    hazard — this documents the schema is fully explicit rather than
    relying on dialect defaults."""
    unbounded = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, String) and column.type.length is None:
                if type(column.type).__name__ == "String":
                    unbounded.append(f"{table.name}.{column.name}")
    assert unbounded == [], f"String columns without an explicit length: {unbounded}"


def test_connect_args_are_database_specific():
    """`check_same_thread` is a sqlite3-specific argument; passing it to
    psycopg2 raises a TypeError, so app.core.database must only set it for
    SQLite URLs."""
    from app.core import database

    configured_url = str(database.engine.url)
    if configured_url.startswith("sqlite"):
        assert database._connect_args == {"check_same_thread": False}
    else:
        assert database._connect_args == {}
