"""Tests for grounding validation (docs Milestone 4, requirement #5/#9/#21)."""
from app.ai.grounding import validate_grounding
from app.ai.schemas import AlternativeExplanation, InvestigationResult

EVIDENCE_PACKET = {
    "candidate_causes": [
        {"cause": "plumbing_leak", "deterministic_score": "high"},
        {"cause": "irrigation_left_active", "deterministic_score": "medium"},
        {"cause": "metering_anomaly", "deterministic_score": "low"},
    ],
    "evidence": [
        {"signal": "baseline_deviation", "value": 238.0, "unit": "percent", "description": "Consumption was 238% above the expected baseline."},
        {"signal": "persistence", "value": 3, "unit": "consecutive_readings", "description": "Persisted for 3 hours."},
        {"signal": "operating_status", "value": "closed", "description": "Location was closed."},
        {"signal": "occupancy", "value": 0, "description": "Occupancy was zero."},
    ],
    "deterministic_metrics": {"actual_consumption": 14.0, "expected_consumption": 1.06, "deviation_pct": 238.0, "z_score": 86.87},
}


def _valid_result(**overrides) -> InvestigationResult:
    defaults = dict(
        likely_cause="plumbing_leak",
        observed=["Consumption was 238% above the expected baseline.", "Occupancy was zero."],
        inference="Elevated, sustained flow while closed and unoccupied is consistent with a continuous leak.",
        supporting_evidence=["baseline_deviation", "operating_status", "occupancy"],
        alternative_explanations=[AlternativeExplanation(cause="irrigation_left_active", why_less_likely="Less consistent with the sustained, flat pattern.")],
        recommended_next_step="Inspect fixtures and the incoming water line for continuous flow.",
        reasoning_confidence="high",
    )
    defaults.update(overrides)
    return InvestigationResult(**defaults)


def test_valid_grounded_response_passes():
    result = validate_grounding(_valid_result(), EVIDENCE_PACKET)
    assert result.valid
    assert result.errors == []


def test_invented_likely_cause_fails():
    result = validate_grounding(_valid_result(likely_cause="ghost_in_the_pipes"), EVIDENCE_PACKET)
    assert not result.valid
    assert any("likely_cause" in e for e in result.errors)


def test_invented_alternative_cause_fails():
    bad = _valid_result(alternative_explanations=[AlternativeExplanation(cause="sabotage", why_less_likely="n/a")])
    result = validate_grounding(bad, EVIDENCE_PACKET)
    assert not result.valid
    assert any("alternative cause" in e for e in result.errors)


def test_invented_supporting_evidence_signal_fails():
    bad = _valid_result(supporting_evidence=["baseline_deviation", "moon_phase"])
    result = validate_grounding(bad, EVIDENCE_PACKET)
    assert not result.valid
    assert any("moon_phase" in e for e in result.errors)


def test_invented_number_in_inference_fails():
    bad = _valid_result(inference="Consumption was approximately 250% above baseline, which is highly suspicious.")
    result = validate_grounding(bad, EVIDENCE_PACKET)
    assert not result.valid
    assert any("ungrounded number" in e for e in result.errors)


def test_referencing_the_actual_evidence_number_passes():
    good = _valid_result(inference="Consumption was 238% above the expected baseline of 1.06, which strongly suggests a leak.")
    result = validate_grounding(good, EVIDENCE_PACKET)
    assert result.valid


def test_small_numbers_like_persistence_hours_are_allowed():
    good = _valid_result(inference="The anomaly persisted for 3 hours while occupancy was 0, consistent with an unattended leak.")
    result = validate_grounding(good, EVIDENCE_PACKET)
    assert result.valid


def test_rounded_number_within_tolerance_passes():
    # 238.0 rounded to 238 in casual text should still match via tolerance.
    good = _valid_result(inference="Consumption was 238% above the expected baseline, consistent with a leak.")
    result = validate_grounding(good, EVIDENCE_PACKET)
    assert result.valid
