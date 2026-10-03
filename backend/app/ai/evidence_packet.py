"""
AI input contract (docs Milestone 4, requirement #3).

Builds the exact structured evidence packet the AI Reasoning Layer (and its
deterministic fallback) receives — assembled entirely from already-computed
deterministic data (`Anomaly.signals`, `Investigation.candidate_causes`,
`Resource`, `Location`). Nothing here is invented or estimated; this
function only reads and reshapes.
"""
from __future__ import annotations

from app.analytics.evidence import evidence_from_signals
from app.models.anomaly import Anomaly
from app.models.investigation import Investigation
from app.models.location import Location
from app.models.resource import Resource


def build_evidence_packet(anomaly: Anomaly, investigation: Investigation, resource: Resource, location: Location) -> dict:
    """
    Build the full structured input the AI (or the deterministic fallback)
    reasons over. Every field is traceable to a deterministic calculation
    from Milestone 3 — see docs/AI_ARCHITECTURE.md, "What the AI sees."
    """
    signals = anomaly.signals

    return {
        "resource": {
            "type": resource.resource_type.value,
            "unit": resource.unit,
        },
        "location": {
            "name": location.name,
        },
        "anomaly": {
            "id": str(anomaly.id),
            "severity": anomaly.severity.value,
            "classification": anomaly.classification.value,
            "window_start": anomaly.window_start.isoformat(),
            "window_end": anomaly.window_end.isoformat(),
        },
        "deterministic_metrics": {
            "actual_consumption": round(signals.get("actual_consumption_mean", 0.0), 3),
            "expected_consumption": round(signals.get("expected_consumption_mean", 0.0), 3),
            "deviation_pct": anomaly.deviation_pct,
            "z_score": round(anomaly.z_score, 2),
            "persistence_count": signals.get("persistence_count"),
            "persistence_hours": signals.get("persistence_hours"),
        },
        "operational_context": {
            "majority_closed_during_window": signals.get("majority_closed"),
            "majority_zero_occupancy_during_window": signals.get("majority_zero_occupancy"),
        },
        "historical_behavior": {
            "baseline_mean": round(signals.get("expected_consumption_mean", 0.0), 3),
            "baseline_stddev": round(signals.get("baseline_stddev_used", 0.0), 3),
            "baseline_sample_count": signals.get("baseline_sample_count"),
            "baseline_confidence": signals.get("baseline_state"),  # "sufficient" | "limited"
        },
        "cross_resource_signals": {
            "correlated_with_other_resource_while_unoccupied": signals.get("cross_resource_correlated"),
        },
        "candidate_causes": investigation.candidate_causes,
        "evidence": evidence_from_signals(signals, anomaly.classification.value),
    }
