"""
Telemetry persistence and querying.

Every ingestion source (simulator, CSV, and any future API push) ends up
calling `get_or_create_location`, `get_or_create_resource`, and
`bulk_insert_measurements` — this is the single place that knows how to
turn a `NormalizedMeasurement` into database rows, which is what keeps the
Intelligence Core (built in later milestones) decoupled from where the data
came from.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.ingestion.schemas import NormalizedMeasurement
from app.ingestion.telemetry_simulator import OperatingHours
from app.models.location import Location
from app.models.measurement import Measurement, MeasurementSource
from app.models.resource import Resource, ResourceType

EXPECTED_UNIT = {ResourceType.ELECTRICITY: "kWh", ResourceType.WATER: "L"}


def _normalize_utc(ts: datetime) -> datetime:
    """Ensure a timestamp is timezone-aware UTC before using it as a dedup key.

    SQLite does not actually persist timezone info even for a
    `DateTime(timezone=True)` column, so a value read back from the
    database can come back naive while newly-generated values are
    tz-aware. Without normalizing both to the same representation here,
    equal timestamps would compare unequal and duplicate-detection would
    silently fail (see tests/ingestion/test_telemetry_service.py).
    """
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def get_or_create_location(
    db: Session, name: str, *, timezone: str = "Asia/Kolkata", operating_hours: OperatingHours | dict | None = None
) -> Location:
    """Fetch a Location by name, or create it if it doesn't exist yet."""
    existing = db.execute(select(Location).where(Location.name == name)).scalar_one_or_none()
    if existing:
        return existing

    hours_json: dict
    if isinstance(operating_hours, OperatingHours):
        hours_json = operating_hours.as_json()
    elif isinstance(operating_hours, dict):
        hours_json = operating_hours
    else:
        hours_json = OperatingHours().as_json()

    location = Location(name=name, timezone=timezone, operating_hours=hours_json)
    db.add(location)
    db.flush()  # assign an id without committing yet
    return location


def get_or_create_resource(db: Session, location_id: UUID, resource_type: ResourceType) -> Resource:
    """Fetch a Resource for (location, resource_type), or create it with the correct unit."""
    existing = db.execute(
        select(Resource).where(Resource.location_id == location_id, Resource.resource_type == resource_type)
    ).scalar_one_or_none()
    if existing:
        return existing

    resource = Resource(location_id=location_id, resource_type=resource_type, unit=EXPECTED_UNIT[resource_type])
    db.add(resource)
    db.flush()
    return resource


def bulk_insert_measurements(
    db: Session, resource_id: UUID, measurements: list[NormalizedMeasurement]
) -> tuple[int, int]:
    """
    Insert measurements for one resource, skipping any (resource, timestamp)
    pair that already exists rather than erroring or silently duplicating.

    Returns (inserted_count, skipped_duplicate_count).

    Rejects any measurement with negative consumption outright — this is
    the single insertion point every ingestion source (CSV, simulator, and
    any future direct/API push) ultimately goes through, so it's the right
    place for this defense-in-depth check even though CSV upload already
    validates this earlier in its own pipeline (docs Milestone 8, "Do not
    silently treat physically impossible negative consumption as valid
    telemetry"). A negative reading is physically impossible for
    electricity or water consumption, so it is rejected rather than
    clamped or silently accepted — clamping would hide a real data-quality
    problem (e.g. a miswired meter or a sign error upstream) instead of
    surfacing it.
    """
    if not measurements:
        return 0, 0

    negative = [m for m in measurements if m.consumption < 0]
    if negative:
        raise ValueError(
            f"Refusing to insert {len(negative)} measurement(s) with negative consumption "
            f"(e.g. {negative[0].consumption} at {negative[0].timestamp.isoformat()}) — "
            "negative consumption is physically impossible and is rejected rather than silently accepted."
        )

    existing_timestamps = {
        _normalize_utc(ts)
        for ts in db.execute(select(Measurement.timestamp).where(Measurement.resource_id == resource_id)).scalars()
    }

    to_insert = []
    skipped = 0
    for m in measurements:
        key = _normalize_utc(m.timestamp)
        if key in existing_timestamps:
            skipped += 1
            continue
        to_insert.append(
            Measurement(
                resource_id=resource_id,
                timestamp=m.timestamp,
                consumption=m.consumption,
                occupancy=m.occupancy,
                operating_status=m.operating_status,
                source=m.source,
                scenario=m.scenario,
            )
        )
        existing_timestamps.add(key)  # guard against duplicates within the same batch too

    if to_insert:
        db.add_all(to_insert)
        db.flush()

    return len(to_insert), skipped


def query_measurements(
    db: Session,
    *,
    resource_id: UUID | None = None,
    location_id: UUID | None = None,
    resource_type: ResourceType | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[Measurement], int]:
    """Filtered, paginated measurement query. Returns (items, total_matching)."""
    query = select(Measurement).join(Resource, Measurement.resource_id == Resource.id)
    count_query = select(func.count(Measurement.id)).join(Resource, Measurement.resource_id == Resource.id)
    conditions = []

    if resource_id is not None:
        conditions.append(Measurement.resource_id == resource_id)
    if location_id is not None:
        conditions.append(Resource.location_id == location_id)
    if resource_type is not None:
        conditions.append(Resource.resource_type == resource_type)
    if start is not None:
        conditions.append(Measurement.timestamp >= start)
    if end is not None:
        conditions.append(Measurement.timestamp < end)

    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total = db.execute(count_query).scalar_one()
    items = (
        db.execute(query.order_by(Measurement.timestamp).offset(offset).limit(limit)).scalars().all()
    )
    return items, total
