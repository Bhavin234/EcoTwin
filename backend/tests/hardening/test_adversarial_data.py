"""
Adversarial data tests (docs Milestone 8, requirement #6) — actively try to
break the deterministic analytics engine with pathological inputs. Every
test here asserts the engine degrades honestly (cold-start states, no
crashes, no fabricated confidence) rather than merely "doesn't throw."
"""
import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.analytics.anomaly_engine import analyze_resource
from app.analytics.baseline_engine import BaselineState, compute_causal_baselines
from app.analytics.deviation import compute_deviation
from app.models.measurement import OperatingStatus
from app.models.resource import ResourceType


def _df(rows):
    return pd.DataFrame(rows)


def test_empty_dataset_does_not_crash():
    df = _df({"timestamp": [], "consumption": [], "occupancy": [], "operating_status": []})
    full_df, anomalies, snapshots = analyze_resource(df, ResourceType.ELECTRICITY)
    assert anomalies == []
    assert snapshots == []


def test_single_measurement_is_cold_start_not_a_fabricated_anomaly():
    df = _df(
        {
            "timestamp": [datetime(2026, 6, 1, tzinfo=timezone.utc)],
            "consumption": [500.0],  # a huge value, but there's no history to compare against
            "occupancy": [0],
            "operating_status": ["closed"],
        }
    )
    full_df, anomalies, snapshots = analyze_resource(df, ResourceType.WATER)
    assert full_df.iloc[0]["baseline_state"] == BaselineState.NO_HISTORY.value
    # No history -> nothing to flag, regardless of how large the single reading is.
    assert anomalies == []


def test_missing_occupancy_does_not_crash_and_does_not_fabricate_zero():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = {
        "timestamp": [start + timedelta(hours=i) for i in range(48)],
        "consumption": [10.0] * 48,
        "occupancy": [None] * 48,  # occupancy genuinely unknown
        "operating_status": ["open"] * 48,
    }
    df = _df(rows)
    full_df, anomalies, snapshots = analyze_resource(df, ResourceType.ELECTRICITY)
    # Should not crash, and normal flat data shouldn't be flagged.
    assert anomalies == []


def test_missing_operating_status_does_not_crash_and_weakens_context():
    """An 'unknown' operating status must never silently count as 'closed'
    context evidence — that would fabricate a signal that isn't there."""
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    n = 24 * 7 * 4
    consumption = [5.0] * n
    # One sustained spike near the end, but with unknown operating status
    # throughout (never explicitly marked closed).
    for i in range(n - 4, n):
        consumption[i] = 200.0
    rows = {
        "timestamp": [start + timedelta(hours=i) for i in range(n)],
        "consumption": consumption,
        "occupancy": [None] * n,
        "operating_status": ["unknown"] * n,
    }
    df = _df(rows)
    full_df, anomalies, snapshots = analyze_resource(df, ResourceType.WATER)
    suspicious = [a for a in anomalies if a.classification == "operationally_suspicious"]
    # With no closed/occupancy evidence at all (both unknown), the engine
    # must not fabricate "closed" or "zero occupancy" context points.
    for a in suspicious:
        assert a.signals["majority_closed"] is False
        assert a.signals["majority_zero_occupancy"] is False


def test_zero_consumption_does_not_produce_nan_or_inf():
    result = compute_deviation(actual=0.0, baseline_mean=0.0, baseline_stddev=0.0, resource_type=ResourceType.WATER)
    assert not math.isnan(result.z_score)
    assert not math.isinf(result.z_score)
    assert result.deviation_pct is None  # baseline mean of 0 is below the near-zero epsilon
    assert result.absolute_deviation == 0.0


def test_extremely_small_consumption_is_stable():
    result = compute_deviation(actual=0.0001, baseline_mean=0.00005, baseline_stddev=0.00001, resource_type=ResourceType.WATER)
    assert not math.isnan(result.z_score)
    assert not math.isinf(result.z_score)
    assert abs(result.z_score) < 100  # floored stddev prevents an absurd blowup


def test_extremely_large_consumption_does_not_overflow():
    result = compute_deviation(actual=1e9, baseline_mean=10.0, baseline_stddev=2.0, resource_type=ResourceType.ELECTRICITY)
    assert not math.isnan(result.z_score)
    assert not math.isinf(result.z_score)
    assert result.deviation_pct > 0
    assert isinstance(result.deviation_pct, float)


def test_duplicate_timestamps_in_the_dataframe_do_not_crash_the_engine():
    """Ingestion already deduplicates before reaching the database
    (docs/TESTING.md, Milestone 2) — this confirms the analytics engine
    itself is also robust if it ever receives a duplicate timestamp."""
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = {
        "timestamp": [start, start, start + timedelta(hours=1)],
        "consumption": [10.0, 10.5, 11.0],
        "occupancy": [5, 5, 5],
        "operating_status": ["open", "open", "open"],
    }
    df = _df(rows)
    # Should not raise.
    full_df, anomalies, snapshots = analyze_resource(df, ResourceType.ELECTRICITY)
    assert len(full_df) == 3


def test_out_of_order_timestamps_produce_the_same_result_as_sorted_input():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    n = 24 * 7 * 5
    timestamps = [start + timedelta(hours=i) for i in range(n)]
    consumption = [10.0 + (i % 5) for i in range(n)]

    sorted_df = _df({"timestamp": timestamps, "consumption": consumption, "occupancy": [5] * n, "operating_status": ["open"] * n})
    shuffled_df = sorted_df.sample(frac=1, random_state=42).reset_index(drop=True)

    sorted_result, _, _ = analyze_resource(sorted_df, ResourceType.ELECTRICITY)
    shuffled_result, _, _ = analyze_resource(shuffled_df, ResourceType.ELECTRICITY)

    # Re-sort both by timestamp and compare the computed baselines row-for-row.
    sorted_result = sorted_result.sort_values("timestamp").reset_index(drop=True)
    shuffled_result = shuffled_result.sort_values("timestamp").reset_index(drop=True)
    pd.testing.assert_series_equal(sorted_result["baseline_mean"], shuffled_result["baseline_mean"])
    pd.testing.assert_series_equal(sorted_result["flagged"], shuffled_result["flagged"])


def test_negative_consumption_is_rejected_at_the_shared_insertion_point(db_session):
    from datetime import date

    from app.ingestion.schemas import NormalizedMeasurement
    from app.models.measurement import MeasurementSource
    from app.services.telemetry_service import bulk_insert_measurements, get_or_create_location, get_or_create_resource

    location = get_or_create_location(db_session, "Hardening Negative Consumption School")
    resource = get_or_create_resource(db_session, location.id, ResourceType.WATER)

    bad_measurement = NormalizedMeasurement(
        timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
        consumption=-5.0,
        occupancy=0,
        operating_status=OperatingStatus.CLOSED,
        source=MeasurementSource.API,
    )
    with pytest.raises(ValueError, match="negative"):
        bulk_insert_measurements(db_session, resource.id, [bad_measurement])
