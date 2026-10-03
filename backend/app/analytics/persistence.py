"""
Persistence detection (docs Milestone 3, requirement #8).

A single unusual reading and a sustained run of unusual readings must be
treated differently — this module turns a per-row "flagged" boolean series
into merged windows, so the rest of the pipeline reasons about incidents,
not individual data points.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.analytics.config import MAX_GAP_INTERVALS_TO_MERGE, PERSISTENCE_POINTS_THRESHOLDS


@dataclass
class FlaggedWindow:
    start: datetime
    end: datetime  # exclusive, one interval past the last flagged reading
    row_indices: list[int]  # positional indices into the source (sorted) DataFrame

    @property
    def persistence_count(self) -> int:
        return len(self.row_indices)


def merge_flagged_windows(df: pd.DataFrame, flagged_column: str = "flagged") -> list[FlaggedWindow]:
    """
    Merge consecutive `True` rows in `flagged_column` into windows.

    `df` must be sorted by timestamp with a regular interval (as produced
    by the telemetry simulator/ingestion). Gaps of up to
    `MAX_GAP_INTERVALS_TO_MERGE` non-flagged rows are still merged into one
    window, so one borderline reading in the middle of a real incident
    doesn't fracture it into separate windows.
    """
    df = df.reset_index(drop=True)
    windows: list[FlaggedWindow] = []
    current_indices: list[int] = []
    gap_count = 0

    for i, flagged in enumerate(df[flagged_column]):
        if flagged:
            current_indices.append(i)
            gap_count = 0
        elif current_indices:
            gap_count += 1
            if gap_count > MAX_GAP_INTERVALS_TO_MERGE:
                windows.append(_build_window(df, current_indices))
                current_indices = []
                gap_count = 0

    if current_indices:
        windows.append(_build_window(df, current_indices))

    return windows


def _build_window(df: pd.DataFrame, indices: list[int]) -> FlaggedWindow:
    start = df.loc[indices[0], "timestamp"]
    last_ts = df.loc[indices[-1], "timestamp"]
    # Infer the interval from the data itself rather than assuming hourly.
    if len(df) > 1:
        interval = df["timestamp"].iloc[1] - df["timestamp"].iloc[0]
    else:
        interval = pd.Timedelta(hours=1)
    end = last_ts + interval
    return FlaggedWindow(start=start, end=end, row_indices=indices)


def persistence_points(persistence_count: int) -> int:
    """Map a raw persistence count to the documented point tiers (config.py)."""
    if persistence_count >= 4:
        return 2
    if persistence_count >= 2:
        return 1
    return 0
