"""
Candidate cause generation (docs/ANOMALY_DETECTION.md, "Cause hypothesis
scoring"; docs Milestone 3, requirement #10).

This is NOT the AI reasoning layer (that's Milestone 4). It's a small,
documented rule table that maps observed signals to plausible causes with
a deterministic high/medium/low rating — the exact `deterministic_score`
values the future AI Reasoning Layer will be given to reason over and
explain, but never allowed to invent or change.
"""
from __future__ import annotations

from app.analytics.severity import ContextSignals
from app.models.resource import ResourceType

Rating = str  # "high" | "medium" | "low"


def generate_candidate_causes(resource_type: ResourceType, context: ContextSignals) -> list[dict]:
    """
    Return a ranked list of `{"cause": ..., "deterministic_score": ...}`
    for one anomaly window, resource-specific per docs Milestone 3,
    requirement #11 (only the rules needed for the MVP scenarios).
    """
    if resource_type == ResourceType.WATER:
        return _water_causes(context)
    return _electricity_causes(context)


def _water_causes(context: ContextSignals) -> list[dict]:
    causes: list[dict[str, str]] = []

    # Elevated + closed + zero occupancy + sustained -> strongly favors a
    # continuous, unattended leak.
    if context.majority_closed and context.majority_zero_occupancy and context.persistence_count >= 2:
        causes.append({"cause": "plumbing_leak", "deterministic_score": "high"})
        causes.append({"cause": "irrigation_left_active", "deterministic_score": "medium"})
        causes.append({"cause": "metering_anomaly", "deterministic_score": "low"})
    # Elevated + zero occupancy but brief -> could still be a leak, but an
    # unattended scheduled process (e.g. irrigation) is at least as likely
    # for a short window.
    elif context.majority_zero_occupancy:
        causes.append({"cause": "irrigation_left_active", "deterministic_score": "high"})
        causes.append({"cause": "plumbing_leak", "deterministic_score": "medium"})
        causes.append({"cause": "metering_anomaly", "deterministic_score": "low"})
    # Elevated with people present -> normal use is the leading explanation.
    else:
        causes.append({"cause": "occupancy_driven", "deterministic_score": "high"})
        causes.append({"cause": "cleaning_activity", "deterministic_score": "medium"})
        causes.append({"cause": "metering_anomaly", "deterministic_score": "low"})

    return causes


def _electricity_causes(context: ContextSignals) -> list[dict]:
    causes: list[dict[str, str]] = []

    if context.majority_closed and context.majority_zero_occupancy and context.persistence_count >= 2:
        causes.append({"cause": "equipment_left_on", "deterministic_score": "high"})
        causes.append({"cause": "hvac_malfunction", "deterministic_score": "medium"})
        causes.append({"cause": "metering_anomaly", "deterministic_score": "low"})
    elif context.majority_zero_occupancy:
        causes.append({"cause": "equipment_left_on", "deterministic_score": "medium"})
        causes.append({"cause": "scheduled_process", "deterministic_score": "medium"})
        causes.append({"cause": "metering_anomaly", "deterministic_score": "low"})
    else:
        causes.append({"cause": "occupancy_driven", "deterministic_score": "high"})
        causes.append({"cause": "scheduled_process", "deterministic_score": "medium"})
        causes.append({"cause": "metering_anomaly", "deterministic_score": "low"})

    return causes
