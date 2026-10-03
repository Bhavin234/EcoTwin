"""Tests for the deviation engine (docs Milestone 3, requirement #4)."""
from app.analytics.deviation import compute_deviation
from app.models.resource import ResourceType


def test_positive_deviation():
    result = compute_deviation(actual=20.0, baseline_mean=10.0, baseline_stddev=1.0, resource_type=ResourceType.ELECTRICITY)
    assert result.z_score > 0
    assert result.deviation_pct == 100.0
    assert result.absolute_deviation == 10.0


def test_negative_deviation():
    result = compute_deviation(actual=5.0, baseline_mean=10.0, baseline_stddev=1.0, resource_type=ResourceType.ELECTRICITY)
    assert result.z_score < 0
    assert result.deviation_pct == -50.0
    assert result.absolute_deviation == -5.0


def test_zero_stddev_does_not_raise_and_uses_floor():
    # No exception, and the floor keeps the z-score finite and sane rather
    # than dividing by zero.
    result = compute_deviation(actual=5.0, baseline_mean=4.0, baseline_stddev=0.0, resource_type=ResourceType.WATER)
    assert result.z_score == (5.0 - 4.0) / 0.15  # MIN_STDDEV_FLOOR for water


def test_near_zero_baseline_mean_suppresses_percentage_but_keeps_zscore():
    # Water baseline near zero (closed-hours standby), a real absolute
    # increase should still register on z-score, but the percentage would
    # be misleadingly huge, so it's None instead.
    result = compute_deviation(actual=14.0, baseline_mean=0.05, baseline_stddev=0.02, resource_type=ResourceType.WATER)
    assert result.deviation_pct is None
    assert result.z_score > 0
    assert result.absolute_deviation > 0


def test_tiny_baseline_with_tiny_actual_does_not_explode():
    result = compute_deviation(actual=0.06, baseline_mean=0.05, baseline_stddev=0.001, resource_type=ResourceType.WATER)
    # Floored stddev prevents an absurd z-score from a trivial 0.01 absolute change.
    assert abs(result.z_score) < 5


def test_no_deviation_gives_zero_zscore():
    result = compute_deviation(actual=10.0, baseline_mean=10.0, baseline_stddev=1.0, resource_type=ResourceType.ELECTRICITY)
    assert result.z_score == 0.0
    assert result.deviation_pct == 0.0
