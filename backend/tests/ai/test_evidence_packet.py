"""Tests for the AI input contract builder (docs Milestone 4, requirement #3)."""
from app.ai.evidence_packet import build_evidence_packet
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.location import Location
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.scenario_runner import run_scenario


def _suspicious_anomaly_for_location(db_session, location_id):
    return (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )


def test_evidence_packet_contains_all_documented_sections(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Evidence Packet School", weeks=6)
    run_analysis_for_location(db_session, result.location_id)

    anomaly = _suspicious_anomaly_for_location(db_session, result.location_id)
    resource = db_session.get(Resource, anomaly.resource_id)
    location = db_session.get(Location, resource.location_id)
    investigation = anomaly.investigation

    packet = build_evidence_packet(anomaly, investigation, resource, location)

    for key in ("resource", "location", "anomaly", "deterministic_metrics", "operational_context", "historical_behavior", "cross_resource_signals", "candidate_causes", "evidence"):
        assert key in packet, f"missing documented section: {key}"

    assert packet["resource"]["type"] == "water"
    assert packet["resource"]["unit"] == "L"
    assert packet["location"]["name"] == "Evidence Packet School"
    assert packet["anomaly"]["classification"] == "operationally_suspicious"
    assert packet["deterministic_metrics"]["actual_consumption"] > packet["deterministic_metrics"]["expected_consumption"]
    assert packet["candidate_causes"][0]["cause"] == "plumbing_leak"
    assert len(packet["evidence"]) >= 1


def test_evidence_packet_numbers_match_the_anomaly_row_exactly(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Evidence Packet School 2", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = _suspicious_anomaly_for_location(db_session, result.location_id)
    resource = db_session.get(Resource, anomaly.resource_id)
    location = db_session.get(Location, resource.location_id)
    packet = build_evidence_packet(anomaly, anomaly.investigation, resource, location)

    assert packet["deterministic_metrics"]["deviation_pct"] == anomaly.deviation_pct
    assert packet["deterministic_metrics"]["z_score"] == round(anomaly.z_score, 2)
