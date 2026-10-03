"""Tests for intervention lifecycle (docs Milestone 5, requirements #6-7)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.intervention import InterventionStatus, VerificationStatus
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.intervention_service import complete_intervention, create_intervention
from app.services.scenario_runner import run_scenario


def _investigated_anomaly(db_session, location_name):
    result = run_scenario(db_session, "water_leak", location_name=location_name, weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )
    investigate_anomaly(db_session, anomaly.id)
    return anomaly


def test_create_intervention_from_investigation(db_session):
    anomaly = _investigated_anomaly(db_session, "Intervention Service School 1")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    assert intervention.status == InterventionStatus.RECOMMENDED
    assert intervention.verification_status == VerificationStatus.PENDING
    assert intervention.marked_complete_at is None


def test_create_intervention_is_idempotent(db_session):
    anomaly = _investigated_anomaly(db_session, "Intervention Service School 2")
    first = create_intervention(db_session, anomaly.investigation.id)
    second = create_intervention(db_session, anomaly.investigation.id)
    assert first.id == second.id


def test_create_intervention_without_recommendation_fails(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Intervention Service School 3", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )
    # Deliberately skip investigate_anomaly() — no Recommendation exists yet.
    with pytest.raises(ValueError, match="Recommendation"):
        create_intervention(db_session, anomaly.investigation.id)


def test_complete_intervention_sets_status_and_timestamp(db_session):
    anomaly = _investigated_anomaly(db_session, "Intervention Service School 4")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    completed_at = datetime(2026, 8, 5, 21, tzinfo=timezone.utc)

    completed = complete_intervention(db_session, intervention.id, completed_at=completed_at)
    assert completed.status == InterventionStatus.COMPLETED
    # SQLite doesn't persist tzinfo even for a DateTime(timezone=True)
    # column (documented in app/services/telemetry_service.py) — compare
    # as naive UTC, matching that documented, expected round-trip.
    assert completed.marked_complete_at.replace(tzinfo=timezone.utc) == completed_at
    assert completed.verification_status == VerificationStatus.PENDING  # completing != verifying


def test_complete_intervention_without_explicit_timestamp_uses_now(db_session):
    anomaly = _investigated_anomaly(db_session, "Intervention Service School 5")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    before = datetime.now(timezone.utc) - timedelta(seconds=2)
    completed = complete_intervention(db_session, intervention.id)
    assert completed.marked_complete_at.replace(tzinfo=timezone.utc) >= before


def test_complete_intervention_twice_is_idempotent_not_an_error(db_session):
    anomaly = _investigated_anomaly(db_session, "Intervention Service School 6")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    first = complete_intervention(db_session, intervention.id, completed_at=datetime(2026, 8, 5, 21, tzinfo=timezone.utc))
    second = complete_intervention(db_session, intervention.id, completed_at=datetime(2026, 8, 6, 21, tzinfo=timezone.utc))
    # Second call is a no-op — original completion timestamp is preserved.
    assert second.marked_complete_at == first.marked_complete_at


def test_complete_unknown_intervention_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        complete_intervention(db_session, uuid.uuid4())


def test_create_intervention_unknown_investigation_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        create_intervention(db_session, uuid.uuid4())
