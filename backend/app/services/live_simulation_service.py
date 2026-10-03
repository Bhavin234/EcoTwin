"""Small, deterministic live telemetry stream for the deployed demo.

The stream advances simulated time rather than pretending to read physical
sensors. It persists readings through the same normalized ingestion path used
by CSV/simulator sources, so the rest of EcoTwin sees ordinary measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion.schemas import NormalizedMeasurement
from app.ingestion.telemetry_simulator import generate_live_batch
from app.models.measurement import Measurement, MeasurementSource
from app.models.resource import Resource, ResourceType
from app.services.telemetry_service import bulk_insert_measurements


@dataclass
class LiveTickResult:
    location_id: UUID
    location_name: str
    inserted: int
    simulated_start: datetime
    simulated_end: datetime
    resources: dict[str, int]


def advance_live_stream(
    db: Session,
    *,
    location_id: UUID,
    hours: int = 1,
    seed: int = 42,
) -> LiveTickResult:
    """Append ``hours`` of deterministic simulated telemetry to a location."""
    from app.models.location import Location

    location = db.get(Location, location_id)
    if location is None:
        raise ValueError(f"Location {location_id} not found")
    if hours < 1 or hours > 24:
        raise ValueError("hours must be between 1 and 24")

    resources = db.query(Resource).filter(Resource.location_id == location_id).all()
    if not resources:
        raise ValueError("Location has no resources")

    latest = db.execute(
        select(func.max(Measurement.timestamp))
        .join(Resource, Measurement.resource_id == Resource.id)
        .where(Resource.location_id == location_id)
    ).scalar_one()
    if latest is None:
        raise ValueError("Location has no telemetry to advance")

    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    else:
        latest = latest.astimezone(timezone.utc)
    start = latest + timedelta(hours=1)

    generated = generate_live_batch(start, hours=hours, seed=seed)
    inserted_by_resource: dict[str, int] = {}

    for resource in resources:
        frame = generated.get(resource.resource_type)
        if frame is None:
            continue
        normalized = [
            NormalizedMeasurement(
                timestamp=row.timestamp,
                consumption=float(row.consumption),
                occupancy=int(row.occupancy) if row.occupancy is not None else None,
                operating_status=row.operating_status,
                source=MeasurementSource.SIMULATOR,
                scenario="live_stream",
            )
            for row in frame.itertuples(index=False)
        ]
        inserted, _ = bulk_insert_measurements(db, resource.id, normalized)
        inserted_by_resource[resource.resource_type.value] = inserted

    db.commit()
    return LiveTickResult(
        location_id=location.id,
        location_name=location.name,
        inserted=sum(inserted_by_resource.values()),
        simulated_start=start,
        simulated_end=start + timedelta(hours=hours - 1),
        resources=inserted_by_resource,
    )
