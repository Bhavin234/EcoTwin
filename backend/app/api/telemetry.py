"""
Telemetry API routes (docs/API.md).

Error responses always follow `{error: {code, message, details?}}` — see
`app.core.errors` for the shared exception handlers that enforce this
shape, including for CSV validation failures.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ingestion.csv_source import CSVValidationError, parse_and_validate_csv
from app.ingestion.scenarios import SCENARIO_NAMES
from app.models.location import Location
from app.models.resource import Resource, ResourceType
from app.schemas.telemetry import (
    CSVUploadResponse,
    LocationOut,
    MeasurementOut,
    PaginatedMeasurements,
    ResourceOut,
    SimulateRequest,
    SimulateResponse,
    LiveTickRequest,
    LiveTickResponse,
)
from app.services.scenario_runner import run_scenario
from app.services.live_simulation_service import advance_live_stream
from app.services.telemetry_service import bulk_insert_measurements, get_or_create_location, get_or_create_resource, query_measurements

router = APIRouter(tags=["telemetry"])


@router.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db)):
    return db.query(Location).order_by(Location.name).all()


@router.get("/resources", response_model=list[ResourceOut])
def list_resources(
    location_id: UUID | None = Query(default=None),
    resource_type: ResourceType | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Resource)
    if location_id is not None:
        query = query.filter(Resource.location_id == location_id)
    if resource_type is not None:
        query = query.filter(Resource.resource_type == resource_type)
    return query.all()


@router.get("/measurements", response_model=PaginatedMeasurements)
def get_measurements(
    resource_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    resource_type: ResourceType | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    items, total = query_measurements(
        db,
        resource_id=resource_id,
        location_id=location_id,
        resource_type=resource_type,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )
    return PaginatedMeasurements(
        items=[MeasurementOut.model_validate(m) for m in items], total=total, limit=limit, offset=offset
    )


@router.post("/data/upload", response_model=CSVUploadResponse)
async def upload_csv(file: UploadFile, db: Session = Depends(get_db)):
    file_bytes = await file.read()

    try:
        parsed_rows = parse_and_validate_csv(file_bytes)
    except CSVValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "csv_validation_failed", "message": "The uploaded CSV failed validation.", "details": exc.errors},
        ) from exc

    locations_created: list[str] = []
    resources_created = 0
    total_inserted = 0
    total_skipped = 0

    # Group rows by (location, resource_type) so each resource is only
    # fetched/created once and measurements are inserted in one batch.
    grouped: dict[tuple[str, ResourceType], list] = {}
    for row in parsed_rows:
        grouped.setdefault((row.location, row.resource_type), []).append(row.measurement)

    known_locations: set[str] = set()
    for (location_name, resource_type), measurements in grouped.items():
        existed = db.query(Location).filter(Location.name == location_name).first() is not None
        location = get_or_create_location(db, location_name)
        if not existed and location_name not in known_locations:
            locations_created.append(location_name)
        known_locations.add(location_name)

        resource_existed = (
            db.query(Resource)
            .filter(Resource.location_id == location.id, Resource.resource_type == resource_type)
            .first()
            is not None
        )
        resource = get_or_create_resource(db, location.id, resource_type)
        if not resource_existed:
            resources_created += 1

        n_inserted, n_skipped = bulk_insert_measurements(db, resource.id, measurements)
        total_inserted += n_inserted
        total_skipped += n_skipped

    db.commit()

    return CSVUploadResponse(
        inserted=total_inserted,
        skipped_duplicates=total_skipped,
        locations_created=locations_created,
        resources_created=resources_created,
    )


@router.post("/data/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest, db: Session = Depends(get_db)):
    if request.scenario not in SCENARIO_NAMES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unknown_scenario",
                "message": f"Unknown scenario '{request.scenario}'.",
                "details": [f"Valid scenarios: {', '.join(SCENARIO_NAMES)}"],
            },
        )

    result = run_scenario(
        db,
        request.scenario,
        location_name=request.location_name,
        seed=request.seed,
        weeks=request.weeks,
    )

    return SimulateResponse(
        scenario=result.scenario,
        location_id=result.location_id,
        location_name=result.location_name,
        inserted=result.inserted,
        skipped_duplicates=result.skipped_duplicates,
        period_start=result.period_start,
        period_end=result.period_end,
    )


@router.post("/data/live/tick", response_model=LiveTickResponse)
def live_tick(request: LiveTickRequest, db: Session = Depends(get_db)):
    """Append the next simulated hours to an existing location.

    This endpoint advances a simulated clock. It does not claim to read
    physical sensors and it does not ask the AI model to invent measurements.
    """
    try:
        result = advance_live_stream(db, location_id=request.location_id, hours=request.hours, seed=request.seed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "live_simulation_failed", "message": str(exc)}) from exc

    return LiveTickResponse(
        location_id=result.location_id,
        location_name=result.location_name,
        inserted=result.inserted,
        simulated_start=result.simulated_start,
        simulated_end=result.simulated_end,
        resources=result.resources,
    )
