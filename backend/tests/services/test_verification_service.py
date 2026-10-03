"""Tests for the verification service (docs Milestone 5, requirements #8-13, #16, #19)."""
import uuid
from datetime import timedelta

import pytest

from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.impact import ImpactKind, ImpactRecord
from app.models.intervention import VerificationStatus
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.intervention_service import complete_intervention, create_intervention
from app.services.scenario_runner import run_scenario
from app.services.verification_service import verify_intervention


def _investigated_anomaly_and_intervention(db_session, location_name, weeks=6):
    result = run_scenario(db_session, "post_intervention_recovery", location_name=location_name, weeks=weeks)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )
    investigate_anomaly(db_session, anomaly.id)
    intervention = create_intervention(db_session, anomaly.investigation.id)
    return anomaly, intervention


def test_genuine_improvement_is_verified(db_session):
    anomaly, intervention = _investigated_anomaly_and_intervention(db_session, "Verification School Verified")
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end)

    outcome = verify_intervention(db_session, intervention.id)

    assert outcome.verification_status == "verified"
    assert outcome.avoided_consumption > 0
    assert outcome.money_saved > 0
    assert outcome.co2e_avoided_kg > 0


def test_verification_persists_a_verified_impact_record(db_session):
    anomaly, intervention = _investigated_anomaly_and_intervention(db_session, "Verification School ImpactRecord")
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end)
    verify_intervention(db_session, intervention.id)

    record = db_session.query(ImpactRecord).filter(ImpactRecord.intervention_id == intervention.id, ImpactRecord.kind == ImpactKind.VERIFIED).first()
    assert record is not None
    assert record.water_saved > 0
    assert record.emission_factor_value_used is not None
    assert record.cost_factor_rate_used is not None


def test_still_elevated_consumption_is_no_measurable_improvement(db_session):
    """Marking the intervention complete *before* the leak window ends
    means the 'post-intervention' window still overlaps the still-elevated
    leak readings — a deliberately dishonest completion timestamp, exactly
    the case the system must not paper over."""
    anomaly, intervention = _investigated_anomaly_and_intervention(db_session, "Verification School NoImprovement")
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_start)

    outcome = verify_intervention(db_session, intervention.id)

    assert outcome.verification_status == "no_measurable_improvement"
    # No verified/estimated savings should be force-fit into a positive number.
    record = db_session.query(ImpactRecord).filter(ImpactRecord.intervention_id == intervention.id, ImpactRecord.kind == ImpactKind.VERIFIED).first()
    assert record is None


def test_insufficient_post_intervention_data_is_reported_honestly(db_session):
    """Completing right at (or after) the end of available telemetry
    leaves no room for a post-intervention window."""
    result = run_scenario(db_session, "post_intervention_recovery", location_name="Verification School Insufficient", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )
    investigate_anomaly(db_session, anomaly.id)
    intervention = create_intervention(db_session, anomaly.investigation.id)

    # Complete far beyond the last available measurement.
    far_future = anomaly.window_end + timedelta(days=30)
    intervention = complete_intervention(db_session, intervention.id, completed_at=far_future)

    outcome = verify_intervention(db_session, intervention.id)
    assert outcome.verification_status == "insufficient_data"
    assert outcome.avoided_consumption is None


def test_verifying_an_incomplete_intervention_raises(db_session):
    anomaly, intervention = _investigated_anomaly_and_intervention(db_session, "Verification School Incomplete")
    with pytest.raises(ValueError, match="not completed"):
        verify_intervention(db_session, intervention.id)


def test_verify_unknown_intervention_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        verify_intervention(db_session, uuid.uuid4())


def test_context_mismatch_downgrades_to_improvement_detected_not_verified(db_session):
    """
    White-box test of the contextual-comparability guard (docs Milestone 5,
    requirement #10): if the anomaly's recorded context doesn't match the
    verification window's actual context, the result must not be labeled
    fully `verified` even though consumption looks normal again. We
    directly alter the persisted anomaly signals to simulate a context
    mismatch, since constructing a full scenario with a genuine mismatch
    would require a seventh simulator scenario dedicated to this one edge
    case.
    """
    anomaly, intervention = _investigated_anomaly_and_intervention(db_session, "Verification School ContextMismatch")
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end)

    # The real verification window is closed/unoccupied; claim the anomaly
    # window was NOT, to force a mismatch.
    mutated_signals = dict(anomaly.signals)
    mutated_signals["majority_closed"] = False
    mutated_signals["majority_zero_occupancy"] = False
    anomaly.signals = mutated_signals
    db_session.commit()

    outcome = verify_intervention(db_session, intervention.id)
    assert outcome.verification_status == "improvement_detected"
