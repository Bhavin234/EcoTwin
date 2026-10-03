"""Tests for the backend demo workflow (docs Milestone 5, requirements #21-22)."""
from app.models.anomaly import Anomaly
from app.models.impact import ImpactRecord
from app.models.intervention import Intervention
from app.models.investigation import Investigation
from app.models.recommendation import Recommendation
from app.services.demo_service import run_demo


def test_run_demo_completes_the_full_greenfield_story(db_session):
    result = run_demo(db_session, location_name="Demo Service School")

    assert result.status == "complete"
    assert result.severity in ("high", "critical")
    assert result.likely_cause == "plumbing_leak"
    assert result.explanation_source in ("ai", "fallback")
    assert result.recommendation_text is not None
    assert result.intervention_id is not None
    assert result.verification_status == "verified"
    assert result.avoided_consumption > 0
    assert result.money_saved > 0
    assert result.co2e_avoided_kg > 0


def test_run_demo_is_idempotent(db_session):
    first = run_demo(db_session, location_name="Demo Service School Idempotent")
    second = run_demo(db_session, location_name="Demo Service School Idempotent")

    assert first.anomaly_id == second.anomaly_id
    assert first.intervention_id == second.intervention_id

    from app.models.location import Location

    location = db_session.query(Location).filter(Location.name == "Demo Service School Idempotent").first()

    investigations = db_session.query(Investigation).join(Anomaly).filter(Anomaly.resource_id.in_(
        [r.id for r in location.resources]
    )).all()
    # Only the suspicious anomaly gets an investigation; there should be
    # exactly one even after calling run_demo() twice.
    assert len(investigations) == 1

    recommendations = db_session.query(Recommendation).filter(Recommendation.investigation_id == investigations[0].id).all()
    assert len(recommendations) == 1

    interventions = db_session.query(Intervention).filter(Intervention.recommendation_id == recommendations[0].id).all()
    assert len(interventions) == 1


def test_run_demo_third_call_does_not_duplicate_impact_records(db_session):
    run_demo(db_session, location_name="Demo Service School TripleRun")
    run_demo(db_session, location_name="Demo Service School TripleRun")
    result = run_demo(db_session, location_name="Demo Service School TripleRun")

    records = db_session.query(ImpactRecord).filter(ImpactRecord.intervention_id == result.intervention_id).all()
    # One estimated + one verified — not accumulating duplicates across 3 runs.
    assert len(records) <= 2


def test_run_demo_result_includes_evidence_fields_for_the_completion_screen(db_session):
    result = run_demo(db_session, location_name="Demo Service School EvidenceFields")
    assert result.resource_type == "water"
    assert result.deviation_pct is not None
    assert result.persistence_hours is not None
    assert result.majority_closed is True
    assert result.majority_zero_occupancy is True


def test_reset_demo_location_removes_all_its_data(db_session):
    from app.models.location import Location
    from app.models.measurement import Measurement
    from app.models.resource import Resource
    from app.services.demo_service import reset_demo_location

    run_demo(db_session, location_name="Demo Service School ToReset")
    was_reset = reset_demo_location(db_session, location_name="Demo Service School ToReset")
    assert was_reset is True

    assert db_session.query(Location).filter(Location.name == "Demo Service School ToReset").first() is None
    remaining_resources = db_session.query(Resource).join(Location, Resource.location_id == Location.id).filter(Location.name == "Demo Service School ToReset").count()
    assert remaining_resources == 0


def test_reset_demo_location_only_affects_the_named_location(db_session):
    from app.models.location import Location
    from app.services.demo_service import reset_demo_location

    run_demo(db_session, location_name="Demo Service School KeepA")
    run_demo(db_session, location_name="Demo Service School KeepB")

    reset_demo_location(db_session, location_name="Demo Service School KeepA")

    assert db_session.query(Location).filter(Location.name == "Demo Service School KeepA").first() is None
    assert db_session.query(Location).filter(Location.name == "Demo Service School KeepB").first() is not None


def test_reset_demo_location_that_does_not_exist_returns_false(db_session):
    from app.services.demo_service import reset_demo_location

    assert reset_demo_location(db_session, location_name="Nonexistent School XYZ") is False


def test_demo_can_run_fresh_again_after_reset(db_session):
    from app.services.demo_service import reset_demo_location

    first = run_demo(db_session, location_name="Demo Service School RerunAfterReset")
    reset_demo_location(db_session, location_name="Demo Service School RerunAfterReset")
    second = run_demo(db_session, location_name="Demo Service School RerunAfterReset")

    # A fresh run produces a *new* anomaly/intervention, not the old IDs.
    assert second.anomaly_id != first.anomaly_id
    assert second.status == "complete"
    assert second.verification_status == "verified"
