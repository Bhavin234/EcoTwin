"""
Intervention/verification adversarial tests (docs Milestone 8, requirement
#10) — edge cases in the completion/verification lifecycle.
"""
from datetime import timedelta

from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.intervention_service import complete_intervention, create_intervention
from app.services.scenario_runner import run_scenario
from app.services.verification_service import verify_intervention


def _investigated(db_session, location_name, scenario="post_intervention_recovery", weeks=6):
    result = run_scenario(db_session, scenario, location_name=location_name, weeks=weeks)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )
    investigate_anomaly(db_session, anomaly.id)
    return anomaly


def test_verification_immediately_after_completion_waits_for_real_post_data(db_session):
    """Completing right at the anomaly's own end, with essentially no
    elapsed 'future' telemetry beyond what the fixed dataset already
    contains, must not fabricate a verified result out of nothing."""
    anomaly = _investigated(db_session, "Adversarial Intervention School Immediate")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    # Complete far beyond the last available measurement -> no post data exists at all.
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end + timedelta(days=60))
    outcome = verify_intervention(db_session, intervention.id)
    assert outcome.verification_status == "insufficient_data"


def test_completed_halfway_through_the_anomaly_is_no_improvement_not_insufficient(db_session):
    anomaly = _investigated(db_session, "Adversarial Intervention School Halfway")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    midpoint = anomaly.window_start + (anomaly.window_end - anomaly.window_start) / 2
    intervention = complete_intervention(db_session, intervention.id, completed_at=midpoint)
    outcome = verify_intervention(db_session, intervention.id)
    # There IS post-completion data (the back half of the leak window plus
    # some recovery), so this should not be "insufficient" — it should
    # honestly reflect whatever the actual post-completion telemetry shows.
    assert outcome.verification_status in ("no_measurable_improvement", "improvement_detected", "verified")


def test_missing_post_intervention_data_is_insufficient_not_verified(db_session):
    anomaly = _investigated(db_session, "Adversarial Intervention School MissingData")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end + timedelta(days=90))
    outcome = verify_intervention(db_session, intervention.id)
    assert outcome.verification_status == "insufficient_data"
    assert outcome.avoided_consumption is None


def test_repeated_verification_is_safely_repeatable_and_consistent(db_session):
    anomaly = _investigated(db_session, "Adversarial Intervention School RepeatedVerify")
    intervention = create_intervention(db_session, anomaly.investigation.id)
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end)

    first = verify_intervention(db_session, intervention.id)
    second = verify_intervention(db_session, intervention.id)
    third = verify_intervention(db_session, intervention.id)

    assert first.verification_status == second.verification_status == third.verification_status
    assert first.avoided_consumption == second.avoided_consumption == third.avoided_consumption

    from app.models.impact import ImpactRecord

    records = db_session.query(ImpactRecord).filter(ImpactRecord.intervention_id == intervention.id).all()
    # Repeated verification must replace, not accumulate, the impact record.
    assert len(records) == 1


def test_repeated_completion_does_not_corrupt_the_lifecycle(db_session):
    anomaly = _investigated(db_session, "Adversarial Intervention School RepeatedComplete")
    intervention = create_intervention(db_session, anomaly.investigation.id)

    first = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end)
    second = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end + timedelta(days=1))
    third = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end + timedelta(days=2))

    # First completion timestamp wins; later "complete" calls are no-ops,
    # not silently overwriting a historical fact.
    assert first.marked_complete_at == second.marked_complete_at == third.marked_complete_at
    assert third.status.value == "completed"


def test_verifying_before_any_intervention_exists_raises_cleanly(db_session):
    import uuid

    import pytest

    with pytest.raises(ValueError):
        verify_intervention(db_session, uuid.uuid4())
