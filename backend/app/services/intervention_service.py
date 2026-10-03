"""
Intervention service (docs Milestone 5, requirements #6-7).

Deliberately small: creating an intervention and marking it complete are
simple lifecycle transitions, not a workflow engine. Verification is a
separate concern — see `app/services/verification_service.py` — and is
never triggered implicitly by completion; a caller must explicitly ask for
it (`POST /api/interventions/{id}/verify`), which keeps "completed" (the
action was reported as done) and "verified" (the telemetry proves it
worked) honestly distinct.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.intervention import Intervention, InterventionStatus, VerificationStatus
from app.models.investigation import Investigation
from app.models.recommendation import Recommendation


def create_intervention(db: Session, investigation_id: UUID) -> Intervention:
    """
    Create an Intervention from an investigation's Recommendation.

    Idempotent: if an Intervention already exists for this investigation's
    recommendation, it's returned unchanged rather than creating a
    duplicate (docs Milestone 5, requirement #22).
    """
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise ValueError(f"Investigation {investigation_id} not found")

    recommendation = db.query(Recommendation).filter(Recommendation.investigation_id == investigation_id).first()
    if recommendation is None:
        raise ValueError(
            f"Investigation {investigation_id} has no Recommendation yet — "
            "run POST /api/anomalies/{anomaly_id}/investigate first."
        )

    existing = db.query(Intervention).filter(Intervention.recommendation_id == recommendation.id).first()
    if existing is not None:
        return existing

    intervention = Intervention(recommendation_id=recommendation.id, status=InterventionStatus.RECOMMENDED)
    db.add(intervention)
    db.commit()
    db.refresh(intervention)
    return intervention


def complete_intervention(db: Session, intervention_id: UUID, completed_at: datetime | None = None) -> Intervention:
    """
    Mark an intervention complete: "the action was reported as performed."
    This alone never sets `verification_status` to anything but `pending`
    — verification is a separate, explicit step.

    `completed_at` defaults to the current time, but callers investigating
    historical/simulated data (e.g. the demo workflow) may pass an
    explicit timestamp so the post-intervention verification window aligns
    with the timeline of the telemetry itself, rather than real wall-clock
    time.
    """
    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise ValueError(f"Intervention {intervention_id} not found")

    if intervention.status == InterventionStatus.COMPLETED:
        # Idempotent no-op rather than erroring on a repeated call.
        return intervention

    intervention.status = InterventionStatus.COMPLETED
    intervention.marked_complete_at = completed_at or datetime.now(timezone.utc)
    intervention.verification_status = VerificationStatus.PENDING
    db.commit()
    db.refresh(intervention)
    return intervention
