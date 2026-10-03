"""Tests for the causal baseline engine (docs Milestone 3, requirement #2/#3)."""
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.analytics.baseline_engine import BaselineState, compute_causal_baselines, latest_slot_baselines


def _hourly_series(start: datetime, hours: int, value_fn) -> pd.DataFrame:
    rows = []
    for i in range(hours):
        ts = start + timedelta(hours=i)
        rows.append({"timestamp": ts, "consumption": value_fn(ts, i)})
    return pd.DataFrame(rows)


def test_no_history_state_for_first_occurrences():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)  # Monday
    df = _hourly_series(start, 24, lambda ts, i: 10.0)
    result = compute_causal_baselines(df)
    # The very first row of the whole series has zero prior history of any kind.
    assert result.iloc[0]["baseline_state"] == BaselineState.NO_HISTORY.value


def test_sufficient_state_after_enough_comparable_slots():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)  # Monday 00:00
    # 6 weeks of identical hourly data -> by week 4, the Monday-00:00 slot
    # has 3 prior comparable samples (weeks 1-3), which meets MIN_SAMPLES_SUFFICIENT.
    df = _hourly_series(start, 24 * 7 * 6, lambda ts, i: 10.0)
    result = compute_causal_baselines(df)
    monday_midnight_rows = result[(result["hour"] == 0) & (result["weekday"] == 0)]
    assert monday_midnight_rows.iloc[3]["baseline_state"] == BaselineState.SUFFICIENT.value
    assert monday_midnight_rows.iloc[3]["baseline_sample_count"] == 3


def test_baseline_does_not_use_the_current_or_future_rows():
    """The defining correctness property: a row's baseline must never
    include its own value or any later value."""
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # Every Monday 00:00 is 10.0, except the very last one (week 6) which
    # is a huge outlier. If the baseline were computed non-causally (using
    # all data including this row), the outlier would pull its own mean up.
    def value_fn(ts, i):
        is_last_monday_midnight = ts.weekday() == 0 and ts.hour == 0 and i >= 24 * 7 * 5
        return 500.0 if is_last_monday_midnight else 10.0

    df = _hourly_series(start, 24 * 7 * 6, value_fn)
    result = compute_causal_baselines(df)
    monday_midnight_rows = result[(result["hour"] == 0) & (result["weekday"] == 0)]
    last_row = monday_midnight_rows.iloc[-1]
    assert last_row["consumption"] == 500.0
    # The baseline for that anomalous row should still reflect the prior
    # normal weeks (~10.0), not be dragged toward 500.
    assert last_row["baseline_mean"] < 20.0


def test_limited_fallback_used_when_slot_history_insufficient_but_resource_has_history():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # Vary consumption by hour so slot-specific data is sparse but overall
    # resource history builds up quickly (every row is a *different* hour
    # for the first day, so no (hour, weekday) slot repeats).
    df = _hourly_series(start, 24 * 10, lambda ts, i: 10.0 + (i % 5))
    result = compute_causal_baselines(df)
    # Row 5 (hour=5 on day 1) is the 6th ever measurement — the (5, Monday)
    # slot has zero prior occurrences, but the resource overall has 5 prior
    # readings, enough for the "limited" global fallback.
    row = result.iloc[5]
    assert row["baseline_state"] == BaselineState.LIMITED.value


def test_latest_slot_baselines_produces_one_snapshot_per_slot():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    df = _hourly_series(start, 24 * 7 * 5, lambda ts, i: 10.0)
    result = compute_causal_baselines(df)
    snapshots = latest_slot_baselines(result)
    # 24 hours * 7 weekdays = 168 distinct slots, all with enough history by week 5.
    assert len(snapshots) == 168
    assert all(s["state"] in ("sufficient", "limited") for s in snapshots)
