"""
Numerical integrity tests (docs Milestone 5, requirement #24).

Confirms that even an AI response that actively tries to state a savings
figure, a CO2e number, or a verification claim has zero effect on the
actual persisted numbers — those always come from
`app/analytics/calculations.py` and `app/services/verification_service.py`,
never from `InvestigationResult`.
"""
import json

from app.ai.investigation_service import investigate_anomaly
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.services.analytics_service import run_analysis_for_location
from app.services.intervention_service import complete_intervention, create_intervention
from app.services.scenario_runner import run_scenario
from app.services.verification_service import verify_intervention

ADVERSARIAL_AI_RESPONSE = {
    "likely_cause": "plumbing_leak",
    "observed": ["Consumption was elevated.", "Occupancy was zero."],
    "inference": (
        "This leak has already cost the school approximately ₹50,000 and 900 kg of CO2e, and is fully verified "
        "as a 95% confidence savings event with 1200 liters recovered."
    ),
    "supporting_evidence": ["baseline_deviation", "operating_status", "occupancy"],
    "alternative_explanations": [{"cause": "irrigation_left_active", "why_less_likely": "Less likely."}],
    "recommended_next_step": "Inspect fixtures and the incoming water line for continuous flow.",
    "reasoning_confidence": "high",
}


def test_adversarial_ai_numbers_never_reach_the_recommendation_or_impact_record(db_session):
    result = run_scenario(db_session, "water_leak", location_name="Numerical Integrity School", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )

    def adversarial_provider(system_prompt, user_prompt):
        # This response fails grounding (invented numbers: 50000, 900,
        # 95, 1200 don't appear in the evidence packet), so it should be
        # rejected and fall back — but even if grounding somehow missed
        # it, the assertions below confirm these numbers still never reach
        # any persisted deterministic field.
        return json.dumps(ADVERSARIAL_AI_RESPONSE)

    outcome = investigate_anomaly(db_session, anomaly.id, ai_provider=adversarial_provider)
    assert outcome.source == "fallback"  # grounding correctly rejected the invented numbers

    recommendation = db_session.query(Recommendation).filter(Recommendation.investigation_id == anomaly.investigation.id).first()
    # The deterministic estimated_saving must be the real computed wastage,
    # not any number the adversarial text tried to assert.
    assert recommendation.estimated_saving != 50000
    assert recommendation.estimated_saving != 1200
    assert recommendation.estimated_saving > 0  # still a real, computed number


def test_verification_status_cannot_be_set_by_ai_text(db_session):
    """Even if an AI response claims something is 'fully verified', only
    app.services.verification_service — never the AI response — determines
    Intervention.verification_status."""
    result = run_scenario(db_session, "water_leak", location_name="Numerical Integrity School 2", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )

    def adversarial_provider(system_prompt, user_prompt):
        return json.dumps(ADVERSARIAL_AI_RESPONSE)

    investigate_anomaly(db_session, anomaly.id, ai_provider=adversarial_provider)
    intervention = create_intervention(db_session, anomaly.investigation.id)

    # Deliberately complete it too early (still inside the leak window) so
    # the deterministic verification MUST report no improvement, directly
    # contradicting the adversarial AI text's "fully verified" claim.
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_start)
    outcome = verify_intervention(db_session, intervention.id)

    assert outcome.verification_status == "no_measurable_improvement"


def test_system_still_calculates_impact_with_ai_completely_unavailable(db_session):
    """AI unavailable end-to-end (no ai_provider, no API key in this test
    environment) — the full recommend/intervene/verify loop must still
    produce correct numbers."""
    result = run_scenario(db_session, "post_intervention_recovery", location_name="Numerical Integrity School 3", weeks=6)
    run_analysis_for_location(db_session, result.location_id)
    anomaly = (
        db_session.query(Anomaly)
        .join(Resource, Anomaly.resource_id == Resource.id)
        .filter(Resource.location_id == result.location_id, Anomaly.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS)
        .first()
    )

    outcome = investigate_anomaly(db_session, anomaly.id)  # no ai_provider -> real default -> no key -> fallback
    assert outcome.source == "fallback"

    intervention = create_intervention(db_session, anomaly.investigation.id)
    intervention = complete_intervention(db_session, intervention.id, completed_at=anomaly.window_end)
    verification = verify_intervention(db_session, intervention.id)

    assert verification.verification_status == "verified"
    assert verification.avoided_consumption > 0
    assert verification.money_saved > 0
    assert verification.co2e_avoided_kg > 0
