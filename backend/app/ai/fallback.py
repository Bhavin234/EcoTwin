"""
Deterministic fallback investigation engine (docs Milestone 4, requirement
#13/#14).

Produces a structurally identical `InvestigationResult` to what the AI
would produce, built entirely from template text and the deterministic
evidence packet — used whenever the AI is unavailable, times out, returns
malformed output, or fails grounding validation. The caller always knows
which path produced a given result via `explanation_source`
("ai" | "fallback") — this module never pretends to be AI output
(docs Milestone 4, requirement #14, "do not fake AI").
"""
from __future__ import annotations

from app.ai.schemas import AlternativeExplanation, InvestigationResult

_CAUSE_DESCRIPTIONS = {
    "plumbing_leak": "a continuous, unattended water leak",
    "irrigation_left_active": "an irrigation system left running outside its intended schedule",
    "metering_anomaly": "a metering or sensor fault rather than genuine consumption",
    "occupancy_driven": "normal consumption from people actually present",
    "cleaning_activity": "a scheduled cleaning or maintenance activity",
    "equipment_left_on": "equipment or HVAC left running outside operating hours",
    "hvac_malfunction": "an HVAC system malfunctioning or stuck on",
    "scheduled_process": "a scheduled automated process running outside occupied hours",
}


def _describe(cause: str) -> str:
    return _CAUSE_DESCRIPTIONS.get(cause, cause.replace("_", " "))


_NEXT_STEP_BY_CAUSE = {
    "plumbing_leak": "Inspect fixtures, toilets, and the incoming water line for continuous flow, starting with the areas nearest this meter.",
    "irrigation_left_active": "Check the irrigation controller's schedule and confirm it is not active during this window.",
    "metering_anomaly": "Cross-check this reading against a secondary meter or manual reading before assuming a real consumption change.",
    "occupancy_driven": "No action needed beyond normal monitoring — the elevated reading is consistent with recorded occupancy.",
    "cleaning_activity": "Confirm this aligns with the scheduled cleaning/maintenance window for this location.",
    "equipment_left_on": "Check HVAC/equipment schedules and verify whether equipment remained active outside operating hours.",
    "hvac_malfunction": "Inspect the HVAC system for a stuck relay or control fault causing it to run outside its schedule.",
    "scheduled_process": "Confirm which automated process is scheduled for this window and whether it ran as expected.",
}


def build_fallback_investigation(evidence_packet: dict) -> InvestigationResult:
    """
    Build a deterministic investigation result from an evidence packet,
    using the already-ranked `candidate_causes` and `evidence` — the exact
    same inputs the AI would have received.
    """
    candidate_causes = evidence_packet.get("candidate_causes", [])
    evidence_list = evidence_packet.get("evidence", [])

    if not candidate_causes:
        # Should not normally happen (an Investigation is only created for
        # operationally_suspicious anomalies, which always have candidate
        # causes) — but never crash if it does.
        return InvestigationResult(
            likely_cause="unknown",
            observed=[e["description"] for e in evidence_list],
            inference="No candidate causes were available to compare against the evidence.",
            supporting_evidence=[e["signal"] for e in evidence_list],
            alternative_explanations=[],
            recommended_next_step="Review the raw telemetry for this window manually.",
            reasoning_confidence="low",
        )

    top = candidate_causes[0]
    alternatives = candidate_causes[1:]

    observed = [e["description"] for e in evidence_list]
    supporting_evidence = [e["signal"] for e in evidence_list]

    inference = (
        f"The available evidence — {', '.join(e['signal'].replace('_', ' ') for e in evidence_list)} — "
        f"is most consistent with {_describe(top['cause'])}, which the deterministic engine rated "
        f"'{top['deterministic_score']}' confidence based on these signals."
    )

    alternative_explanations = [
        AlternativeExplanation(
            cause=alt["cause"],
            why_less_likely=(
                f"Rated '{alt['deterministic_score']}' confidence by the deterministic engine — "
                f"less consistent with the observed signals than {_describe(top['cause'])}."
            ),
        )
        for alt in alternatives
    ]

    reasoning_confidence = {"high": "high", "medium": "medium", "low": "low"}.get(top["deterministic_score"], "medium")

    return InvestigationResult(
        likely_cause=top["cause"],
        observed=observed,
        inference=inference,
        supporting_evidence=supporting_evidence,
        alternative_explanations=alternative_explanations,
        recommended_next_step=_NEXT_STEP_BY_CAUSE.get(top["cause"], "Investigate this location's telemetry and physical systems further."),
        reasoning_confidence=reasoning_confidence,
    )
