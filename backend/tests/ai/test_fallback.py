"""Tests for the deterministic fallback investigation engine (docs Milestone 4, requirement #13)."""
from app.ai.fallback import build_fallback_investigation
from app.ai.grounding import validate_grounding

EVIDENCE_PACKET = {
    "candidate_causes": [
        {"cause": "plumbing_leak", "deterministic_score": "high"},
        {"cause": "irrigation_left_active", "deterministic_score": "medium"},
        {"cause": "metering_anomaly", "deterministic_score": "low"},
    ],
    "evidence": [
        {"signal": "baseline_deviation", "value": 238.0, "unit": "percent", "description": "Consumption was 238% above the expected baseline."},
        {"signal": "persistence", "value": 3, "unit": "consecutive_readings", "description": "Persisted for 3 hours (3 consecutive readings)."},
        {"signal": "operating_status", "value": "closed", "description": "Location was closed."},
        {"signal": "occupancy", "value": 0, "description": "Occupancy was zero."},
        {"signal": "classification", "value": "operationally_suspicious", "description": "Classified as operationally suspicious."},
    ],
}


def test_fallback_uses_the_top_ranked_candidate_cause():
    result = build_fallback_investigation(EVIDENCE_PACKET)
    assert result.likely_cause == "plumbing_leak"
    assert result.reasoning_confidence == "high"


def test_fallback_lists_remaining_causes_as_alternatives():
    result = build_fallback_investigation(EVIDENCE_PACKET)
    alt_causes = {a.cause for a in result.alternative_explanations}
    assert alt_causes == {"irrigation_left_active", "metering_anomaly"}


def test_fallback_observed_matches_evidence_descriptions():
    result = build_fallback_investigation(EVIDENCE_PACKET)
    evidence_descriptions = {e["description"] for e in EVIDENCE_PACKET["evidence"]}
    assert set(result.observed) == evidence_descriptions


def test_fallback_passes_its_own_grounding_check():
    """The fallback is a deterministic template, but it must still satisfy
    the exact same grounding rules the AI path is held to — no double
    standard."""
    result = build_fallback_investigation(EVIDENCE_PACKET)
    grounding = validate_grounding(result, EVIDENCE_PACKET)
    assert grounding.valid, grounding.errors


def test_fallback_recommends_a_cause_specific_next_step():
    result = build_fallback_investigation(EVIDENCE_PACKET)
    assert "water" in result.recommended_next_step.lower() or "fixture" in result.recommended_next_step.lower() or "line" in result.recommended_next_step.lower()


def test_fallback_handles_empty_candidate_causes_without_crashing():
    result = build_fallback_investigation({"candidate_causes": [], "evidence": []})
    assert result.likely_cause == "unknown"
    assert result.reasoning_confidence == "low"
