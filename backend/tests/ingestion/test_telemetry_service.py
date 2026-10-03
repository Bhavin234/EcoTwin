"""Tests for the telemetry persistence/query service."""
from datetime import datetime, timezone

from app.ingestion.schemas import NormalizedMeasurement
from app.models.measurement import MeasurementSource, OperatingStatus
from app.models.resource import ResourceType
from app.services.telemetry_service import (
    bulk_insert_measurements,
    get_or_create_location,
    get_or_create_resource,
    query_measurements,
)


def _measurement(hour: int, consumption: float) -> NormalizedMeasurement:
    return NormalizedMeasurement(
        timestamp=datetime(2026, 6, 1, hour, tzinfo=timezone.utc),
        consumption=consumption,
        occupancy=5,
        operating_status=OperatingStatus.OPEN,
        source=MeasurementSource.API,
    )


def test_get_or_create_location_is_idempotent(db_session):
    loc1 = get_or_create_location(db_session, "Service Test School")
    loc2 = get_or_create_location(db_session, "Service Test School")
    assert loc1.id == loc2.id


def test_get_or_create_resource_uses_correct_unit(db_session):
    location = get_or_create_location(db_session, "Service Test School 2")
    resource = get_or_create_resource(db_session, location.id, ResourceType.WATER)
    assert resource.unit == "L"


def test_bulk_insert_skips_duplicates(db_session):
    location = get_or_create_location(db_session, "Service Test School 3")
    resource = get_or_create_resource(db_session, location.id, ResourceType.ELECTRICITY)

    measurements = [_measurement(8, 10.0), _measurement(9, 12.0)]
    inserted, skipped = bulk_insert_measurements(db_session, resource.id, measurements)
    assert (inserted, skipped) == (2, 0)

    # Re-inserting the same measurements should skip both.
    inserted2, skipped2 = bulk_insert_measurements(db_session, resource.id, measurements)
    assert (inserted2, skipped2) == (0, 2)


def test_query_measurements_filters_by_resource_and_date(db_session):
    location = get_or_create_location(db_session, "Service Test School 4")
    resource = get_or_create_resource(db_session, location.id, ResourceType.WATER)
    bulk_insert_measurements(
        db_session, resource.id, [_measurement(h, float(h)) for h in range(6, 12)]
    )

    items, total = query_measurements(
        db_session,
        resource_id=resource.id,
        start=datetime(2026, 6, 1, 8, tzinfo=timezone.utc),
        end=datetime(2026, 6, 1, 10, tzinfo=timezone.utc),
    )
    assert total == 2
    assert {m.timestamp.hour for m in items} == {8, 9}
