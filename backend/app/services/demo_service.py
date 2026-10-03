"""
Backend demo workflow (docs Milestone 5, requirement #21-22).

This is the function a future frontend "Run EcoTwin Demo" button will
call — not built yet (Milestone 6+), but the complete backend workflow it
needs already exists here. Safe to call repeatedly: each step first checks
whether it has already happened and resumes from wherever the location
currently stands, rather than restarting from scratch or duplicating rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.intervention import Intervention, InterventionStatus
from app.models.location import Location
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.intervention_service import complete_intervention, create_intervention
from app.services.scenario_runner import run_scenario
from app.services.verification_service import verify_intervention

_SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}


@dataclass
class DemoResult:
    status: str  # "no_anomaly_found" | "complete"
    location_id: UUID | None
    location_name: str
    anomaly_id: UUID | None = None
    resource_type: str | None = None
    severity: str | None = None
    explanation_source: str | None = None
    likely_cause: str | None = None
    deviation_pct: float | None = None
    z_score: float | None = None
    persistence_hours: float | None = None
    majority_closed: bool | None = None
    majority_zero_occupancy: bool | None = None
    recommendation_text: str | None = None
    intervention_id: UUID | None = None
    verification_status: str | None = None
    avoided_consumption: float | None = None
    money_saved: float | None = None
    co2e_avoided_kg: float | None = None
    message: str = ""


def _top_suspicious_anomaly(db: Session, location_id: UUID) -> Anomaly | None:
    anomalies = (
        db.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .all()
    )
    if not anomalies:
        return None
    return max(anomalies, key=lambda a: _SEVERITY_RANK.get(a.severity.value, -1))


def run_demo(
    db: Session,
    *,
    scenario: str = "post_intervention_recovery",
    location_name: str = "Greenfield Public School",
    ai_provider: Callable[[str, str], str] | None = None,
) -> DemoResult:
    """
    Run (or resume) the full EcoTwin demo workflow for one location:
    seed -> analyze -> investigate -> recommend -> intervene -> complete ->
    verify -> return a structured summary.
    """
    location = db.query(Location).filter(Location.name == location_name).first()
    if location is None:
        result = run_scenario(db, scenario, location_name=location_name)
        location = db.get(Location, result.location_id)

    # Only run the (destructive, full-replace) analytics pass if this
    # location doesn't have any anomalies yet — re-running it on every demo
    # call would wipe any investigation/recommendation/intervention
    # progress already made (docs Milestone 5, requirement #22).
    has_any_anomaly = (
        db.query(Anomaly).join(Resource, Anomaly.resource_id == Resource.id).filter(Resource.location_id == location.id).first()
        is not None
    )
    if not has_any_anomaly:
        run_analysis_for_location(db, location.id)

    anomaly = _top_suspicious_anomaly(db, location.id)
    if anomaly is None:
        return DemoResult(
            status="no_anomaly_found",
            location_id=location.id,
            location_name=location.name,
            message="No operationally_suspicious anomaly was found for this location/scenario.",
        )

    investigation = anomaly.investigation
    if investigation.explanation is None:
        outcome = investigate_anomaly(db, anomaly.id, ai_provider=ai_provider)
        likely_cause = outcome.result.likely_cause
        explanation_source = outcome.source
    else:
        likely_cause = investigation.top_cause
        explanation_source = investigation.explanation_source.value

    recommendation = db.query(Recommendation).filter(Recommendation.investigation_id == investigation.id).first()

    intervention = create_intervention(db, investigation.id)
    if intervention.status != InterventionStatus.COMPLETED:
        # Use the anomaly's own window_end as the completion timestamp —
        # this is what makes the pre-generated "recovery" telemetry in the
        # demo dataset line up as the post-intervention verification
        # window, rather than waiting for real wall-clock time to pass.
        intervention = complete_intervention(db, intervention.id, completed_at=anomaly.window_end)

    verification = verify_intervention(db, intervention.id)

    return DemoResult(
        status="complete",
        location_id=location.id,
        location_name=location.name,
        anomaly_id=anomaly.id,
        resource_type=anomaly.resource.resource_type.value,
        severity=anomaly.severity.value,
        explanation_source=explanation_source,
        likely_cause=likely_cause,
        deviation_pct=anomaly.deviation_pct,
        z_score=anomaly.z_score,
        persistence_hours=anomaly.signals.get("persistence_hours"),
        majority_closed=anomaly.signals.get("majority_closed"),
        majority_zero_occupancy=anomaly.signals.get("majority_zero_occupancy"),
        recommendation_text=recommendation.action_text if recommendation else None,
        intervention_id=intervention.id,
        verification_status=verification.verification_status,
        avoided_consumption=verification.avoided_consumption,
        money_saved=verification.money_saved,
        co2e_avoided_kg=verification.co2e_avoided_kg,
        message=verification.message,
    )


def reset_demo_location(db: Session, location_name: str = "Greenfield Public School") -> bool:
    """
    Fully remove one location's data (measurements, baselines, anomalies,
    investigations, recommendations, interventions, impact records,
    resources, and the location itself) so the next `run_demo()` call
    starts genuinely fresh — for judges who want to watch the full story
    happen again from scratch, not just re-confirm cached results (docs
    Milestone 7, requirement #16-17).

    Deliberately scoped to *this one location* rather than a blanket
    database wipe (`python -m app.cli seed-demo --reset` already exists
    for that, at the developer/CLI level) — this must never touch any
    other location's data. Returns False if the location doesn't exist
    (nothing to reset).
    """
    from app.models.baseline import Baseline
    from app.models.impact import ImpactRecord
    from app.models.intervention import Intervention
    from app.models.investigation import Investigation
    from app.models.measurement import Measurement
    from app.models.recommendation import Recommendation

    location = db.query(Location).filter(Location.name == location_name).first()
    if location is None:
        return False

    resource_ids = [r.id for r in db.query(Resource).filter(Resource.location_id == location.id).all()]
    if resource_ids:
        anomaly_ids = [a.id for a in db.query(Anomaly).filter(Anomaly.resource_id.in_(resource_ids)).all()]
        investigation_ids = [
            i.id for i in db.query(Investigation).filter(Investigation.anomaly_id.in_(anomaly_ids)).all()
        ] if anomaly_ids else []
        recommendation_ids = [
            r.id for r in db.query(Recommendation).filter(Recommendation.investigation_id.in_(investigation_ids)).all()
        ] if investigation_ids else []

        db.query(ImpactRecord).filter(ImpactRecord.resource_id.in_(resource_ids)).delete(synchronize_session=False)
        if recommendation_ids:
            db.query(Intervention).filter(Intervention.recommendation_id.in_(recommendation_ids)).delete(synchronize_session=False)
        if investigation_ids:
            db.query(Recommendation).filter(Recommendation.investigation_id.in_(investigation_ids)).delete(synchronize_session=False)
        if anomaly_ids:
            db.query(Investigation).filter(Investigation.anomaly_id.in_(anomaly_ids)).delete(synchronize_session=False)
        db.query(Anomaly).filter(Anomaly.resource_id.in_(resource_ids)).delete(synchronize_session=False)
        db.query(Baseline).filter(Baseline.resource_id.in_(resource_ids)).delete(synchronize_session=False)
        db.query(Measurement).filter(Measurement.resource_id.in_(resource_ids)).delete(synchronize_session=False)
        db.query(Resource).filter(Resource.location_id == location.id).delete(synchronize_session=False)

    db.query(Location).filter(Location.id == location.id).delete(synchronize_session=False)
    db.commit()
    return True
