"""
Analytics API routes (docs/API.md, Milestone 3 endpoints).

No AI is involved anywhere in this file (docs Milestone 3, requirement
#20) — every response here is deterministic output from
`app.analytics` / `app.services.analytics_service` / `app.services.factor_service`.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.anomaly import Anomaly, AnomalyClassification, AnomalyStatus, Severity
from app.models.baseline import Baseline
from app.models.factors import CostFactor, EmissionFactor
from app.models.resource import Resource, ResourceType
from app.schemas.analytics import (
    AnomalyDetailOut,
    AnomalyOut,
    BaselineOut,
    CostFactorOut,
    EmissionFactorOut,
    FactorsOut,
    RunAnalysisRequest,
    RunAnalysisResponse,
    UpdateCostFactorRequest,
    UpdateEmissionFactorRequest,
)
from app.services.analytics_service import run_analysis_for_location
from app.services.factor_service import ensure_default_factors

router = APIRouter(tags=["analytics"])


@router.post("/analysis/run", response_model=RunAnalysisResponse)
def run_analysis(request: RunAnalysisRequest, db: Session = Depends(get_db)):
    try:
        result = run_analysis_for_location(db, request.location_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "location_not_found", "message": str(exc)}) from exc

    return RunAnalysisResponse(
        location_id=result.location_id,
        location_name=result.location_name,
        resources=[r.__dict__ for r in result.resources],
    )


@router.get("/anomalies", response_model=list[AnomalyOut])
def list_anomalies(
    resource_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    resource_type: ResourceType | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    status: AnomalyStatus | None = Query(default=None),
    classification: AnomalyClassification | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Anomaly).join(Resource, Anomaly.resource_id == Resource.id)
    if resource_id is not None:
        query = query.filter(Anomaly.resource_id == resource_id)
    if location_id is not None:
        query = query.filter(Resource.location_id == location_id)
    if resource_type is not None:
        query = query.filter(Resource.resource_type == resource_type)
    if severity is not None:
        query = query.filter(Anomaly.severity == severity)
    if status is not None:
        query = query.filter(Anomaly.status == status)
    if classification is not None:
        query = query.filter(Anomaly.classification == classification)

    return query.order_by(Anomaly.detected_at.desc()).all()


@router.get("/anomalies/{anomaly_id}", response_model=AnomalyDetailOut)
def get_anomaly(anomaly_id: UUID, db: Session = Depends(get_db)):
    from app.analytics.evidence import evidence_from_signals

    anomaly = (
        db.query(Anomaly).options(joinedload(Anomaly.investigation)).filter(Anomaly.id == anomaly_id).first()
    )
    if anomaly is None:
        raise HTTPException(status_code=404, detail={"code": "anomaly_not_found", "message": "No such anomaly."})

    # `evidence` is not stored — it's deterministically regenerated from the
    # persisted `signals` every time (see app/analytics/evidence.py), the
    # same function the AI Reasoning Layer's evidence packet uses, so what
    # a person sees here is provably the same evidence the AI reasoned
    # over (docs Milestone 6, requirement #13; docs/AI_ARCHITECTURE.md).
    evidence = evidence_from_signals(anomaly.signals, anomaly.classification.value)

    return AnomalyDetailOut(
        **AnomalyOut.model_validate(anomaly).model_dump(),
        signals=anomaly.signals,
        evidence=evidence,
        investigation=anomaly.investigation,
    )


@router.get("/resources/{resource_id}/baselines", response_model=list[BaselineOut])
def get_resource_baselines(resource_id: UUID, db: Session = Depends(get_db)):
    """
    Read-only access to the persisted baseline snapshots for a resource
    (docs Milestone 6 — added so the frontend can show "current vs.
    baseline" without recomputing anything client-side; baselines are
    written by POST /api/analysis/run and never computed in the browser).
    """
    return db.query(Baseline).filter(Baseline.resource_id == resource_id).all()


@router.get("/config/factors", response_model=FactorsOut)
def get_factors(db: Session = Depends(get_db)):
    ensure_default_factors(db)
    return FactorsOut(
        cost_factors=db.query(CostFactor).all(),
        emission_factors=db.query(EmissionFactor).all(),
    )


@router.put("/config/factors/cost/{factor_id}", response_model=CostFactorOut)
def update_cost_factor(factor_id: UUID, request: UpdateCostFactorRequest, db: Session = Depends(get_db)):
    factor = db.get(CostFactor, factor_id)
    if factor is None:
        raise HTTPException(status_code=404, detail={"code": "factor_not_found", "message": "No such cost factor."})
    factor.rate = request.rate
    db.commit()
    db.refresh(factor)
    return factor


@router.put("/config/factors/emission/{factor_id}", response_model=EmissionFactorOut)
def update_emission_factor(factor_id: UUID, request: UpdateEmissionFactorRequest, db: Session = Depends(get_db)):
    factor = db.get(EmissionFactor, factor_id)
    if factor is None:
        raise HTTPException(status_code=404, detail={"code": "factor_not_found", "message": "No such emission factor."})
    factor.factor_value = request.factor_value
    if request.source is not None:
        factor.source = request.source
    if request.version is not None:
        factor.version = request.version
    db.commit()
    db.refresh(factor)
    return factor
