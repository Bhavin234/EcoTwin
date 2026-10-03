"""
Runs a named simulator scenario and persists the result, so both the
`/api/data/simulate` endpoint and the `seed-demo` CLI command share one
code path rather than duplicating insertion logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.schemas import NormalizedMeasurement
from app.ingestion.scenarios import ScenarioResult, generate_scenario
from app.ingestion.telemetry_simulator import SimulatorConfig
from app.models.measurement import MeasurementSource
from app.models.resource import ResourceType
from app.services.telemetry_service import bulk_insert_measurements, get_or_create_location, get_or_create_resource


@dataclass
class ScenarioRunResult:
    scenario: str
    location_id: UUID
    location_name: str
    inserted: dict[str, int]
    skipped_duplicates: dict[str, int]
    period_start: date
    period_end: date


def run_scenario(
    db: Session,
    scenario_name: str,
    *,
    location_name: str = "Greenfield Public School",
    seed: int | None = None,
    weeks: int | None = None,
) -> ScenarioRunResult:
    """Generate `scenario_name` and persist it under `location_name`."""
    config = SimulatorConfig()
    if seed is not None:
        config.seed = seed
    if weeks is not None:
        config.weeks = weeks

    result: ScenarioResult = generate_scenario(scenario_name, config)

    location = get_or_create_location(
        db, location_name, operating_hours=config.operating_hours
    )

    inserted: dict[str, int] = {}
    skipped: dict[str, int] = {}

    for resource_type, df in result.measurements.items():
        resource = get_or_create_resource(db, location.id, resource_type)
        normalized = [
            NormalizedMeasurement(
                timestamp=row.timestamp,
                consumption=row.consumption,
                occupancy=row.occupancy,
                operating_status=row.operating_status,
                source=MeasurementSource.SIMULATOR,
                scenario=scenario_name,
            )
            for row in df.itertuples(index=False)
        ]
        n_inserted, n_skipped = bulk_insert_measurements(db, resource.id, normalized)
        inserted[resource_type.value] = n_inserted
        skipped[resource_type.value] = n_skipped

    db.commit()

    return ScenarioRunResult(
        scenario=scenario_name,
        location_id=location.id,
        location_name=location.name,
        inserted=inserted,
        skipped_duplicates=skipped,
        period_start=config.start_date,
        period_end=config.end_date,
    )
