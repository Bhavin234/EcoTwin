"""Tests for recommendation generation (docs Milestone 5, requirements #3-5)."""
from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.impact import ImpactKind, ImpactRecord
from app.models.recommendation import Priority, Recommendation
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.scenario_runner import run_scenario


def _suspicious_anomaly(db_session, location_id):
    return (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )


def test_recommendation_created_after_investigation_water(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Rec Service School Water", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = _suspicious_anomaly(db_session, result.location_id)

    investigate_anomaly(db_session, anomaly.id)

    recommendation = db_session.query(Recommendation).filter(Recommendation.investigation_id == anomaly.investigation.id).first()
    assert recommendation is not None
    assert "water" in recommendation.action_text.lower() or "fixture" in recommendation.action_text.lower() or "line" in recommendation.action_text.lower()
    assert recommendation.estimated_saving is not None
    assert recommendation.estimated_saving > 0


def test_recommendation_created_after_investigation_electricity(db_session):
    result = run_scenario(db_session, "electricity_overconsumption", location_name="Rec Service School Elec", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = _suspicious_anomaly(db_session, result.location_id)

    investigate_anomaly(db_session, anomaly.id)

    recommendation = db_session.query(Recommendation).filter(Recommendation.investigation_id == anomaly.investigation.id).first()
    assert recommendation is not None
    assert recommendation.estimated_saving > 0


def test_recommendation_priority_derived_from_severity(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Rec Service School Priority", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = _suspicious_anomaly(db_session, result.location_id)

    investigate_anomaly(db_session, anomaly.id)
    recommendation = db_session.query(Recommendation).filter(Recommendation.investigation_id == anomaly.investigation.id).first()

    if anomaly.severity.value in ("critical", "high"):
        assert recommendation.priority == Priority.HIGH
    elif anomaly.severity.value == "medium":
        assert recommendation.priority == Priority.MEDIUM
    else:
        assert recommendation.priority == Priority.LOW


def test_estimated_impact_record_created_with_factor_snapshot(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Rec Service School Impact", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = _suspicious_anomaly(db_session, result.location_id)

    investigate_anomaly(db_session, anomaly.id)

    record = db_session.query(ImpactRecord).filter(ImpactRecord.anomaly_id == anomaly.id, ImpactRecord.kind == ImpactKind.ESTIMATED).first()
    assert record is not None
    assert record.water_saved > 0
    assert record.money_saved > 0
    assert record.co2e_avoided_kg > 0
    assert record.cost_factor_rate_used is not None
    assert record.emission_factor_value_used is not None
    assert record.emission_factor_version is not None


def test_recommendation_not_duplicated_on_second_investigate_call(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Rec Service School NoDupe", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = _suspicious_anomaly(db_session, result.location_id)

    investigate_anomaly(db_session, anomaly.id)
    investigate_anomaly(db_session, anomaly.id, force=True)  # force re-investigation

    recommendations = db_session.query(Recommendation).filter(Recommendation.investigation_id == anomaly.investigation.id).all()
    assert len(recommendations) == 1

    impact_records = (
        db_session.query(ImpactRecord).filter(ImpactRecord.anomaly_id == anomaly.id, ImpactRecord.kind == ImpactKind.ESTIMATED).all()
    )
    assert len(impact_records) == 1
