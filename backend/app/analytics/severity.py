"""
Severity + classification scoring (docs/ANOMALY_DETECTION.md, "Severity
levels" and "'Unusual' vs 'operationally suspicious'").

This is a small, fully documented point system — not a single
deviation-percentage threshold. Three independent signal groups each
contribute 0-3 points; the total maps to a severity level, and a separate,
narrower rule decides the `unusual` vs `operationally_suspicious`
classification. Every point awarded is traceable to a specific signal, so
"why did this become HIGH rather than MEDIUM" always has a concrete answer
(docs Milestone 3, requirement #7).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.anomaly import AnomalyClassification, Severity


@dataclass(frozen=True)
class ContextSignals:
    """The contextual signals gathered for one anomaly window."""

    max_abs_z_score: float
    persistence_count: int
    majority_closed: bool  # operating_status was "closed" for most of the window
    majority_zero_occupancy: bool  # occupancy was 0 for most of the window
    cross_resource_correlated: bool  # the other resource at the same location also flagged an overlapping window


@dataclass(frozen=True)
class SeverityResult:
    severity: Severity
    classification: AnomalyClassification
    deviation_points: int
    persistence_points: int
    context_points: int
    total_points: int
    context_signals_present: list[str]  # names of the context signals that actually fired, for evidence/explainability


def _deviation_points(max_abs_z_score: float) -> int:
    """Magnitude of the statistical deviation. See ANOMALY_DETECTION.md, 'Deviation'."""
    if max_abs_z_score >= 6.0:
        return 3
    if max_abs_z_score >= 3.5:
        return 2
    if max_abs_z_score >= 2.0:
        return 1
    return 0


def _persistence_points(persistence_count: int) -> int:
    """How long the deviation lasted. See ANOMALY_DETECTION.md, 'Persistence'."""
    if persistence_count >= 4:
        return 2
    if persistence_count >= 2:
        return 1
    return 0


def _context_points(signals: ContextSignals) -> tuple[int, list[str]]:
    """
    Contextual signals that make elevated consumption operationally
    suspicious rather than merely statistically unusual.

    Each contributes independently:
      - `closed`: consumption was elevated while the building was marked
        closed — nobody should have been generating this load.
      - `zero_occupancy`: consumption was elevated with nobody present —
        counted separately from `closed` because a location can have
        zero occupancy without formally being "closed" (e.g. between
        scheduled activities).
      - `cross_resource_correlated`, but *only* when occupancy was also
        zero: two resources moving together while occupied is often just
        a busy period (see docs, 'Occupancy... elevated consumption with
        high occupancy is downweighted'); two resources moving together
        while unoccupied is a stronger signal of a systemic/equipment
        cause and is scored accordingly.
    """
    present: list[str] = []
    points = 0
    if signals.majority_closed:
        points += 1
        present.append("closed_during_window")
    if signals.majority_zero_occupancy:
        points += 1
        present.append("zero_occupancy_during_window")
    if signals.cross_resource_correlated and signals.majority_zero_occupancy:
        points += 1
        present.append("cross_resource_correlated")
    return points, present


def score_anomaly(signals: ContextSignals) -> SeverityResult:
    """
    Combine the three signal groups into a total point score, map it to a
    severity level, and separately decide the unusual/operationally
    suspicious classification.

    Severity thresholds (max 8 points: 3 deviation + 2 persistence + 3 context):
        0-1 -> LOW
        2-3 -> MEDIUM
        4-6 -> HIGH
        7-8 -> CRITICAL

    Classification: `operationally_suspicious` requires BOTH persistence
    (2+ consecutive flagged readings) AND at least one contextual signal
    (closed / zero occupancy / cross-resource-while-unoccupied). This
    directly implements ANOMALY_DETECTION.md's definition: "unusual AND
    persistent AND inconsistent with expected operating context." A large
    but brief or fully-occupied deviation (e.g. the legitimate-spike
    scenario) can still reach a high *severity* score from magnitude alone,
    but will not be classified `operationally_suspicious` — it stays
    `unusual`, and is not promoted to a full Investigation
    (docs/ANOMALY_DETECTION.md, "'Unusual' vs 'operationally suspicious'").
    """
    deviation_points = _deviation_points(signals.max_abs_z_score)
    persistence_points = _persistence_points(signals.persistence_count)
    context_points, context_signals_present = _context_points(signals)

    total = deviation_points + persistence_points + context_points

    if total >= 7:
        severity = Severity.CRITICAL
    elif total >= 4:
        severity = Severity.HIGH
    elif total >= 2:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    is_operationally_suspicious = persistence_points >= 1 and context_points >= 1
    classification = (
        AnomalyClassification.OPERATIONALLY_SUSPICIOUS
        if is_operationally_suspicious
        else AnomalyClassification.UNUSUAL
    )

    return SeverityResult(
        severity=severity,
        classification=classification,
        deviation_points=deviation_points,
        persistence_points=persistence_points,
        context_points=context_points,
        total_points=total,
        context_signals_present=context_signals_present,
    )
