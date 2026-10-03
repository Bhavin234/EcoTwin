"""Tests for severity + classification scoring (docs Milestone 3, requirement #6/#7)."""
from app.analytics.severity import ContextSignals, score_anomaly
from app.models.anomaly import AnomalyClassification, Severity


def test_low_severity_single_reading_no_context():
    signals = ContextSignals(
        max_abs_z_score=2.1, persistence_count=1, majority_closed=False, majority_zero_occupancy=False, cross_resource_correlated=False
    )
    result = score_anomaly(signals)
    assert result.severity == Severity.LOW
    assert result.classification == AnomalyClassification.UNUSUAL


def test_medium_severity_sustained_but_no_context():
    signals = ContextSignals(
        max_abs_z_score=2.5, persistence_count=2, majority_closed=False, majority_zero_occupancy=False, cross_resource_correlated=False
    )
    result = score_anomaly(signals)
    assert result.severity == Severity.MEDIUM
    # Persistent (1 point) but zero context points -> still not operationally suspicious.
    assert result.classification == AnomalyClassification.UNUSUAL


def test_high_severity_with_one_strong_context_signal():
    signals = ContextSignals(
        max_abs_z_score=4.0, persistence_count=3, majority_closed=True, majority_zero_occupancy=False, cross_resource_correlated=False
    )
    result = score_anomaly(signals)
    assert result.severity == Severity.HIGH
    assert result.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS


def test_critical_severity_multiple_agreeing_context_signals():
    signals = ContextSignals(
        max_abs_z_score=8.0, persistence_count=5, majority_closed=True, majority_zero_occupancy=True, cross_resource_correlated=True
    )
    result = score_anomaly(signals)
    assert result.severity == Severity.CRITICAL
    assert result.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS
    assert result.total_points == 8


def test_large_but_brief_and_occupied_deviation_stays_unusual_not_suspicious():
    """The core false-positive-avoidance property: a big statistical
    deviation alone (e.g. a legitimate busy period) must not be classified
    operationally_suspicious without persistence + context."""
    signals = ContextSignals(
        max_abs_z_score=9.0, persistence_count=1, majority_closed=False, majority_zero_occupancy=False, cross_resource_correlated=False
    )
    result = score_anomaly(signals)
    # Severity can still be elevated from magnitude alone...
    assert result.severity in (Severity.MEDIUM, Severity.HIGH)
    # ...but it must not be promoted to operationally_suspicious.
    assert result.classification == AnomalyClassification.UNUSUAL


def test_cross_resource_correlation_only_counts_when_unoccupied():
    occupied = ContextSignals(
        max_abs_z_score=3.0, persistence_count=2, majority_closed=False, majority_zero_occupancy=False, cross_resource_correlated=True
    )
    unoccupied = ContextSignals(
        max_abs_z_score=3.0, persistence_count=2, majority_closed=False, majority_zero_occupancy=True, cross_resource_correlated=True
    )
    occupied_result = score_anomaly(occupied)
    unoccupied_result = score_anomaly(unoccupied)
    assert occupied_result.context_points == 0
    assert unoccupied_result.context_points == 2  # zero_occupancy + cross_resource_correlated


def test_context_signals_present_lists_exactly_what_fired():
    signals = ContextSignals(
        max_abs_z_score=5.0, persistence_count=3, majority_closed=True, majority_zero_occupancy=True, cross_resource_correlated=False
    )
    result = score_anomaly(signals)
    assert set(result.context_signals_present) == {"closed_during_window", "zero_occupancy_during_window"}
