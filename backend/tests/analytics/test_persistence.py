"""Tests for persistence detection (docs Milestone 3, requirement #8)."""
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.analytics.persistence import merge_flagged_windows, persistence_points


def _df(flags: list[bool]) -> pd.DataFrame:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(hours=i) for i in range(len(flags))],
            "flagged": flags,
        }
    )


def test_single_unusual_reading_is_its_own_short_window():
    df = _df([False, False, True, False, False])
    windows = merge_flagged_windows(df)
    assert len(windows) == 1
    assert windows[0].persistence_count == 1


def test_sustained_anomaly_is_one_window():
    df = _df([False, True, True, True, True, False])
    windows = merge_flagged_windows(df)
    assert len(windows) == 1
    assert windows[0].persistence_count == 4


def test_interrupted_anomaly_with_small_gap_is_merged():
    # One non-flagged reading in the middle of an otherwise-flagged run is
    # still merged into a single window (MAX_GAP_INTERVALS_TO_MERGE = 1).
    df = _df([True, True, False, True, True])
    windows = merge_flagged_windows(df)
    assert len(windows) == 1
    assert windows[0].persistence_count == 4


def test_two_separate_anomalies_with_large_gap_stay_separate():
    df = _df([True, True, False, False, False, True, True])
    windows = merge_flagged_windows(df)
    assert len(windows) == 2


def test_no_flags_produces_no_windows():
    df = _df([False, False, False])
    assert merge_flagged_windows(df) == []


def test_persistence_points_tiers():
    assert persistence_points(1) == 0
    assert persistence_points(2) == 1
    assert persistence_points(3) == 1
    assert persistence_points(4) == 2
    assert persistence_points(10) == 2
