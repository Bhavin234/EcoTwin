"""
Evidence Engine (docs/ANOMALY_DETECTION.md, "Evidence packet construction";
docs Milestone 3, requirement #9).

Turns the deterministic signals that produced a severity/classification
decision into a structured, human-legible evidence list. This is the exact
data structure — not a separately-written narrative — that will be shown
to users and passed to the AI Reasoning Layer in Milestone 4, so a person
can verify EcoTwin's reasoning independently of any AI-generated text.
"""
from __future__ import annotations

from app.analytics.severity import ContextSignals


def build_evidence(
    *,
    deviation_pct: float | None,
    z_score: float,
    persistence_count: int,
    persistence_hours: float,
    context: ContextSignals,
    classification: str,
) -> list[dict]:
    """
    Build the ordered evidence list for one anomaly window. Every entry's
    `value` is a deterministic number or category already computed
    elsewhere in the pipeline — this function only formats and describes,
    it never computes anything new.

    Takes `classification` as a plain string (rather than the full
    `SeverityResult`) so this function can be re-run later purely from an
    `Anomaly`'s persisted `signals` — see `evidence_from_anomaly()` below —
    without needing to recompute severity scoring.
    """
    evidence: list[dict] = []

    if deviation_pct is not None:
        evidence.append(
            {
                "signal": "baseline_deviation",
                "value": round(deviation_pct, 1),
                "unit": "percent",
                "description": f"Consumption was {deviation_pct:.0f}% above the expected baseline for this time slot.",
            }
        )
    else:
        evidence.append(
            {
                "signal": "baseline_deviation_zscore",
                "value": round(z_score, 1),
                "unit": "z_score",
                "description": (
                    "The expected baseline for this time slot is very close to zero, so a percentage "
                    f"isn't meaningful; the deviation is {z_score:.1f} standard deviations above what's expected."
                ),
            }
        )

    evidence.append(
        {
            "signal": "persistence",
            "value": persistence_count,
            "unit": "consecutive_readings",
            "description": f"The elevated reading persisted for {persistence_hours:.0f} hour(s) ({persistence_count} consecutive readings), not a single spike.",
        }
    )

    if context.majority_closed:
        evidence.append(
            {
                "signal": "operating_status",
                "value": "closed",
                "description": "The location was marked closed for most of this window.",
            }
        )

    if context.majority_zero_occupancy:
        evidence.append(
            {
                "signal": "occupancy",
                "value": 0,
                "description": "Recorded occupancy was zero for most of this window.",
            }
        )

    if context.cross_resource_correlated and context.majority_zero_occupancy:
        evidence.append(
            {
                "signal": "cross_resource_correlation",
                "value": True,
                "description": "The other monitored resource at this location also showed an overlapping anomaly while unoccupied, suggesting a systemic or equipment-related cause.",
            }
        )

    evidence.append(
        {
            "signal": "classification",
            "value": classification,
            "description": (
                "Classified as operationally suspicious: unusual, persistent, and inconsistent with expected operating context."
                if classification == "operationally_suspicious"
                else "Classified as unusual: a statistically significant deviation, but not persistent and/or contextually inconsistent enough to be operationally suspicious."
            ),
        }
    )

    return evidence


def context_signals_from_stored(signals: dict) -> ContextSignals:
    """Reconstruct a `ContextSignals` from an `Anomaly.signals` JSON blob (see anomaly_engine.py)."""
    return ContextSignals(
        max_abs_z_score=signals["max_abs_z_score"],
        persistence_count=signals["persistence_count"],
        majority_closed=signals["majority_closed"],
        majority_zero_occupancy=signals["majority_zero_occupancy"],
        cross_resource_correlated=signals["cross_resource_correlated"],
    )


def evidence_from_signals(signals: dict, classification: str) -> list[dict]:
    """
    Rebuild the evidence list purely from an already-persisted `Anomaly.signals`
    dict and its classification — used by the AI Reasoning Layer (Milestone 4)
    and by the API so evidence never needs a separate storage copy: it is
    always regenerated deterministically from the same signals that drove
    the original severity/classification decision.
    """
    context = context_signals_from_stored(signals)
    return build_evidence(
        deviation_pct=signals.get("deviation_pct"),
        z_score=signals["max_abs_z_score"],
        persistence_count=signals["persistence_count"],
        persistence_hours=signals["persistence_hours"],
        context=context,
        classification=classification,
    )
