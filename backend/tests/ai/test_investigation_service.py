"""
Investigation service tests (docs Milestone 4, requirement #21) — every
test here uses a mock AI provider; none require a real Anthropic API call
or a real API key.
"""
import json

import pytest

from app.ai.client import AIClientError, AITimeoutError
from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.services.analytics_service import run_analysis_for_location
from app.services.scenario_runner import run_scenario


def _seed_suspicious_anomaly(db_session, location_name: str):
    """Seed a water-leak scenario and run analytics, returning the
    operationally_suspicious water anomaly the Greenfield story relies on.

    Filters by this test's own location: the shared session-scoped test
    database accumulates anomalies from earlier tests too, so an
    unfiltered query would risk returning a different test's
    already-investigated (cached) anomaly instead of a fresh one.
    """
    from app.models.resource import Resource

    result = run_scenario(db_session, "water_leak", location_name=location_name, weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )
    assert anomaly is not None, "test setup assumption failed: expected an operationally_suspicious anomaly"
    return anomaly


VALID_AI_RESPONSE = {
    "likely_cause": "plumbing_leak",
    "observed": ["Consumption was well above the expected baseline.", "Occupancy was zero."],
    "inference": "Sustained elevated flow while the building was closed and unoccupied points to a continuous leak rather than normal use.",
    "supporting_evidence": ["baseline_deviation", "operating_status", "occupancy"],
    "alternative_explanations": [{"cause": "irrigation_left_active", "why_less_likely": "Less consistent with a flat, sustained pattern than a leak."}],
    "recommended_next_step": "Inspect fixtures and the incoming water line for continuous flow.",
    "reasoning_confidence": "high",
}


def test_valid_ai_response_is_accepted_and_persisted(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School Valid")

    def mock_provider(system_prompt, user_prompt):
        return json.dumps(VALID_AI_RESPONSE)

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=mock_provider)
    assert outcome.source == "ai"
    assert outcome.result.likely_cause == "plumbing_leak"
    assert outcome.investigation.explanation_source.value == "ai"
    assert outcome.investigation.explanation["likely_cause"] == "plumbing_leak"


def test_malformed_json_triggers_fallback(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School Malformed")

    def mock_provider(system_prompt, user_prompt):
        return "this is not json at all {{"

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=mock_provider)
    assert outcome.source == "fallback"
    assert outcome.fallback_reason is not None
    assert outcome.investigation.explanation_source.value == "fallback"


def test_schema_violation_triggers_fallback(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School BadSchema")

    def mock_provider(system_prompt, user_prompt):
        return json.dumps({"likely_cause": "plumbing_leak"})  # missing every other required field

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=mock_provider)
    assert outcome.source == "fallback"


def test_ungrounded_invented_cause_triggers_fallback(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School Ungrounded")
    bad_response = dict(VALID_AI_RESPONSE, likely_cause="alien_intervention")

    def mock_provider(system_prompt, user_prompt):
        return json.dumps(bad_response)

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=mock_provider)
    assert outcome.source == "fallback"
    assert "alien_intervention" not in outcome.result.likely_cause


def test_markdown_fenced_json_is_still_parsed(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School Fenced")

    def mock_provider(system_prompt, user_prompt):
        return "```json\n" + json.dumps(VALID_AI_RESPONSE) + "\n```"

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=mock_provider)
    assert outcome.source == "ai"


def test_ai_timeout_triggers_fallback(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School Timeout")

    def mock_provider(system_prompt, user_prompt):
        raise AITimeoutError("request timed out")

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=mock_provider)
    assert outcome.source == "fallback"
    assert "timed out" in outcome.fallback_reason


def test_generic_api_failure_triggers_fallback(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School APIFail")

    def mock_provider(system_prompt, user_prompt):
        raise AIClientError("rate limited")

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=mock_provider)
    assert outcome.source == "fallback"


def test_missing_api_key_uses_fallback_via_default_provider(db_session):
    """No ai_provider passed at all — exercises the real default path
    (app.ai.client.call_anthropic), which must fall back cleanly when no
    ANTHROPIC_API_KEY is configured (as in this test environment)."""
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School NoKey")
    outcome = investigate_anomaly(db_session, anomaly.id)
    assert outcome.source == "fallback"
    assert "ANTHROPIC_API_KEY" in outcome.fallback_reason


def test_second_call_returns_cached_result_without_calling_provider_again(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School Cache")
    call_count = {"n": 0}

    def counting_provider(system_prompt, user_prompt):
        call_count["n"] += 1
        return json.dumps(VALID_AI_RESPONSE)

    investigate_anomaly(db_session, anomaly.id, ai_provider=counting_provider)
    investigate_anomaly(db_session, anomaly.id, ai_provider=counting_provider)
    assert call_count["n"] == 1


def test_force_reinvokes_the_provider(db_session):
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School Force")
    call_count = {"n": 0}

    def counting_provider(system_prompt, user_prompt):
        call_count["n"] += 1
        return json.dumps(VALID_AI_RESPONSE)

    investigate_anomaly(db_session, anomaly.id, ai_provider=counting_provider)
    investigate_anomaly(db_session, anomaly.id, ai_provider=counting_provider, force=True)
    assert call_count["n"] == 2


def test_cannot_investigate_a_merely_unusual_anomaly(db_session):
    result = run_scenario(db_session, "normal_operation", location_name="AI Test School Unusual", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    unusual_anomaly = (
        db_session.query(Anomaly)
        .filter(Anomaly.classification == AnomalyClassification.UNUSUAL)
        .first()
    )
    if unusual_anomaly is None:
        pytest.skip("normal_operation scenario produced no 'unusual' anomalies to test against in this run")

    with pytest.raises(ValueError, match="operationally_suspicious"):
        investigate_anomaly(db_session, unusual_anomaly.id)


def test_unknown_anomaly_id_raises(db_session):
    import uuid

    with pytest.raises(ValueError, match="not found"):
        investigate_anomaly(db_session, uuid.uuid4())


def test_evidence_packet_is_actually_passed_to_the_provider(db_session):
    """Confirms the candidate causes and evidence actually reach the provider call, not a placeholder."""
    anomaly = _seed_suspicious_anomaly(db_session, "AI Test School EvidenceCheck")
    captured = {}

    def capturing_provider(system_prompt, user_prompt):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return json.dumps(VALID_AI_RESPONSE)

    investigate_anomaly(db_session, anomaly.id, ai_provider=capturing_provider)

    assert "candidate_causes" in captured["user_prompt"]
    assert "plumbing_leak" in captured["user_prompt"]
    assert "evidence" in captured["user_prompt"]
    assert "NEVER invent" in captured["system_prompt"]
