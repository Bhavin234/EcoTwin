"""
Intervention/verification/impact API routes (docs/API.md, Milestone 5).

Thin wrappers around app.services.intervention_service /
verification_service — no business logic lives in this file.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.impact import ImpactRecord
from app.models.resource import ResourceType
from app.schemas.intervention import (
    CompleteInterventionRequest,
    ImpactRecordOut,
    ImpactResponse,
    ImpactSummaryOut,
    InterventionOut,
    VerifyInterventionResponse,
)
from app.services.intervention_service import complete_intervention, create_intervention
from app.services.verification_service import verify_intervention

router = APIRouter(tags=["intervention"])


def _value_error_to_http(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 404 if "not found" in message else 422
    code = "not_found" if status_code == 404 else "invalid_request"
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


@router.post("/investigations/{investigation_id}/interventions", response_model=InterventionOut)
def create_intervention_route(investigation_id: UUID, db: Session = Depends(get_db)):
    try:
        return create_intervention(db, investigation_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/interventions/{intervention_id}", response_model=InterventionOut)
def get_intervention(intervention_id: UUID, db: Session = Depends(get_db)):
    from app.models.intervention import Intervention

    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "No such intervention."})
    return intervention


@router.post("/interventions/{intervention_id}/complete", response_model=InterventionOut)
def complete_intervention_route(intervention_id: UUID, request: CompleteInterventionRequest = CompleteInterventionRequest(), db: Session = Depends(get_db)):
    try:
        return complete_intervention(db, intervention_id, completed_at=request.completed_at)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/interventions/{intervention_id}/verify", response_model=VerifyInterventionResponse)
def verify_intervention_route(intervention_id: UUID, db: Session = Depends(get_db)):
    try:
        outcome = verify_intervention(db, intervention_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    return VerifyInterventionResponse(
        intervention_id=intervention_id,
        verification_status=outcome.verification_status,
        window_start=outcome.window_start,
        window_end=outcome.window_end,
        actual_post_consumption_mean=outcome.actual_post_consumption_mean,
        ordinary_baseline_mean=outcome.ordinary_baseline_mean,
        ordinary_baseline_state=outcome.ordinary_baseline_state,
        counterfactual_rate=outcome.counterfactual_rate,
        avoided_consumption=outcome.avoided_consumption,
        money_saved=outcome.money_saved,
        co2e_avoided_kg=outcome.co2e_avoided_kg,
        message=outcome.message,
    )


@router.get("/impact", response_model=ImpactResponse)
def get_impact(
    location_id: UUID | None = Query(default=None),
    resource_type: ResourceType | None = Query(default=None),
    db: Session = Depends(get_db),
):
    from app.models.resource import Resource

    query = db.query(ImpactRecord)
    if location_id is not None:
        query = query.join(Resource, ImpactRecord.resource_id == Resource.id).filter(Resource.location_id == location_id)
    if resource_type is not None:
        query = query.join(Resource, ImpactRecord.resource_id == Resource.id).filter(Resource.resource_type == resource_type)

    records = query.all()

    summary_by_kind: dict[str, dict] = {}
    for record in records:
        kind = record.kind.value
        bucket = summary_by_kind.setdefault(
            kind, {"total_money_saved": 0.0, "total_co2e_avoided_kg": 0.0, "total_water_saved": 0.0, "total_energy_saved": 0.0, "record_count": 0}
        )
        bucket["total_money_saved"] += record.money_saved or 0.0
        bucket["total_co2e_avoided_kg"] += record.co2e_avoided_kg or 0.0
        bucket["total_water_saved"] += record.water_saved or 0.0
        bucket["total_energy_saved"] += record.energy_saved or 0.0
        bucket["record_count"] += 1

    summary = [ImpactSummaryOut(kind=kind, **totals) for kind, totals in summary_by_kind.items()]

    return ImpactResponse(summary=summary, records=records)
