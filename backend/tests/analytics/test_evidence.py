"""Tests for evidence generation (docs Milestone 3, requirement #9)."""
from app.analytics.evidence import build_evidence
from app.analytics.severity import ContextSignals, score_anomaly


def test_evidence_includes_percentage_when_meaningful():
    context = ContextSignals(max_abs_z_score=5.0, persistence_count=3, majority_closed=True, majority_zero_occupancy=True, cross_resource_correlated=False)
    severity_result = score_anomaly(context)
    evidence = build_evidence(
        deviation_pct=238.0, z_score=5.0, persistence_count=3, persistence_hours=3.0, context=context, classification=severity_result.classification.value
    )
    deviation_items = [e for e in evidence if e["signal"] == "baseline_deviation"]
    assert len(deviation_items) == 1
    assert deviation_items[0]["value"] == 238.0
    assert "238%" in deviation_items[0]["description"]


def test_evidence_uses_zscore_when_percentage_not_meaningful():
    context = ContextSignals(max_abs_z_score=6.0, persistence_count=3, majority_closed=True, majority_zero_occupancy=True, cross_resource_correlated=False)
    severity_result = score_anomaly(context)
    evidence = build_evidence(
        deviation_pct=None, z_score=6.0, persistence_count=3, persistence_hours=3.0, context=context, classification=severity_result.classification.value
    )
    assert any(e["signal"] == "baseline_deviation_zscore" for e in evidence)
    assert not any(e["signal"] == "baseline_deviation" for e in evidence)


def test_evidence_includes_context_items_only_when_present():
    context = ContextSignals(max_abs_z_score=3.0, persistence_count=2, majority_closed=False, majority_zero_occupancy=False, cross_resource_correlated=False)
    severity_result = score_anomaly(context)
    evidence = build_evidence(
        deviation_pct=50.0, z_score=3.0, persistence_count=2, persistence_hours=2.0, context=context, classification=severity_result.classification.value
    )
    signals_present = {e["signal"] for e in evidence}
    assert "operating_status" not in signals_present
    assert "occupancy" not in signals_present


def test_evidence_reflects_classification():
    context = ContextSignals(max_abs_z_score=6.0, persistence_count=4, majority_closed=True, majority_zero_occupancy=True, cross_resource_correlated=False)
    severity_result = score_anomaly(context)
    evidence = build_evidence(
        deviation_pct=300.0, z_score=6.0, persistence_count=4, persistence_hours=4.0, context=context, classification=severity_result.classification.value
    )
    classification_item = next(e for e in evidence if e["signal"] == "classification")
    assert classification_item["value"] == "operationally_suspicious"
