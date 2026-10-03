"""
AI grounding adversarial tests (docs Milestone 8, requirement #8) — actively
try to smuggle fabricated numbers, causes, evidence, savings claims, and
false "verified" claims through the AI Reasoning Layer, and confirm every
one is rejected (falls back) and never reaches any persisted field.
"""
import json

from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.intervention import VerificationStatus
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.intervention_service import complete_intervention, create_intervention
from app.services.scenario_runner import run_scenario
from app.services.verification_service import verify_intervention

VALID_RESPONSE = {
    "likely_cause": "plumbing_leak",
    "observed": ["Consumption was well above the expected baseline.", "Occupancy was zero."],
    "inference": "Sustained elevated flow while closed and unoccupied points to a continuous leak.",
    "supporting_evidence": ["baseline_deviation", "operating_status", "occupancy"],
    "alternative_explanations": [{"cause": "irrigation_left_active", "why_less_likely": "Less consistent with the pattern."}],
    "recommended_next_step": "Inspect fixtures and the incoming water line for continuous flow.",
    "reasoning_confidence": "high",
}


def _suspicious_anomaly(db_session, location_name):
    result = run_scenario(db_session, "water_leak", location_name=location_name, weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )
    assert anomaly is not None
    return anomaly


def test_invented_percentage_number_is_rejected(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Invented Pct")
    bad = dict(VALID_RESPONSE, inference="Consumption increased by exactly 500%, an extraordinary spike.")

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: json.dumps(bad))
    assert outcome.source == "fallback"
    assert "500" not in json.dumps(outcome.investigation.explanation)


def test_invented_cause_not_in_candidate_list_is_rejected(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Invented Cause")
    bad = dict(VALID_RESPONSE, likely_cause="solar_inverter_failure")

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: json.dumps(bad))
    assert outcome.source == "fallback"
    assert outcome.investigation.top_cause != "solar_inverter_failure"


def test_invented_evidence_signal_is_rejected(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Invented Evidence")
    bad = dict(VALID_RESPONSE, supporting_evidence=["baseline_deviation", "sensor_voltage_increase"])

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: json.dumps(bad))
    assert outcome.source == "fallback"


def test_invented_savings_claim_is_rejected_and_never_persisted(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Invented Savings")
    bad = dict(VALID_RESPONSE, inference="This leak has already cost the school \u20b950,000 in wasted water.")

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: json.dumps(bad))
    assert outcome.source == "fallback"

    from app.models.recommendation import Recommendation

    recommendation = db_session.query(Recommendation).filter(Recommendation.investigation_id == anomaly.investigation.id).first()
    assert recommendation.estimated_saving != 50000


def test_fake_verification_claim_in_ai_text_has_zero_effect_on_verification_status(db_session):
    """The AI claiming something is 'fully verified' must have no bearing
    on Intervention.verification_status — only verify_intervention() does."""
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Fake Verified")
    bad = dict(VALID_RESPONSE, inference="This intervention is fully verified and confirmed successful.")

    investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: json.dumps(bad))
    intervention = create_intervention(db_session, anomaly.investigation.id)

    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_start)
    outcome = verify_intervention(db_session, intervention.id)

    assert outcome.verification_status == "no_measurable_improvement"
    assert intervention.verification_status == VerificationStatus.NO_MEASURABLE_IMPROVEMENT


def test_empty_ai_response_string_falls_back(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Empty Response")
    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: "")
    assert outcome.source == "fallback"


def test_ai_response_missing_required_field_falls_back(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Missing Field")
    incomplete = {k: v for k, v in VALID_RESPONSE.items() if k != "reasoning_confidence"}
    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: json.dumps(incomplete))
    assert outcome.source == "fallback"


def test_ai_response_with_wrong_confidence_value_falls_back(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Bad Confidence")
    bad = dict(VALID_RESPONSE, reasoning_confidence="99% certain")
    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: json.dumps(bad))
    assert outcome.source == "fallback"


def test_ai_response_wrapped_in_extra_prose_falls_back_if_unparseable(db_session):
    anomaly = _suspicious_anomaly(db_session, "Adversarial AI School Extra Prose")
    wrapped = "Sure, here's my analysis:\n\n" + json.dumps(VALID_RESPONSE) + "\n\nLet me know if you need anything else!"
    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=lambda s, u: wrapped)
    assert outcome.source == "fallback"
