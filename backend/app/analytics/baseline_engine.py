"""
Baseline Engine (docs/ANOMALY_DETECTION.md, "Baseline calculation").

Computes, for every measurement, "what would we reasonably expect
consumption to be under comparable conditions?" — using only data that
came *before* that measurement (causal), so a measurement is never used to
compute its own expected value. This matters specifically because our
demo/scenario data contains an anomaly late in the series: if the baseline
for a (hour, weekday) slot were computed from *all* historical data
including the anomalous readings themselves, the anomaly would quietly
dilute its own baseline instead of standing out against it.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

import pandas as pd

from app.analytics.config import (
    GLOBAL_FALLBACK_MIN_SAMPLES,
    GLOBAL_FALLBACK_WINDOW,
    MIN_SAMPLES_SUFFICIENT,
    ROLLING_WINDOW_SLOTS,
)


class BaselineState(str, Enum):
    """Distinguishes a trustworthy baseline from a fallback from no data at all."""

    SUFFICIENT = "sufficient"  # enough same-hour/same-weekday history to use directly
    LIMITED = "limited"  # not enough slot-specific history; falls back to a resource-wide baseline
    NO_HISTORY = "no_history"  # no usable history at all yet — no baseline, no fabricated confidence


@dataclass(frozen=True)
class BaselineEstimate:
    mean: float | None
    stddev: float | None
    sample_count: int
    state: BaselineState


def compute_causal_baselines(measurements: pd.DataFrame) -> pd.DataFrame:
    """
    Add `baseline_mean`, `baseline_stddev`, `baseline_sample_count`, and
    `baseline_state` columns to a measurements DataFrame (columns required:
    `timestamp`, `consumption`).

    Each row's baseline is computed strictly from earlier rows — the
    rolling window described in ANOMALY_DETECTION.md, evaluated causally.

    Robust to an empty input (docs Milestone 8, adversarial data testing):
    returns an empty DataFrame with the expected columns rather than
    raising, so callers never need to special-case "no measurements yet"
    before calling this.
    """
    if measurements.empty:
        return measurements.assign(
            hour=pd.Series(dtype="int64"),
            weekday=pd.Series(dtype="int64"),
            baseline_mean=pd.Series(dtype="float64"),
            baseline_stddev=pd.Series(dtype="float64"),
            baseline_sample_count=pd.Series(dtype="int64"),
            baseline_state=pd.Series(dtype="object"),
        )

    df = measurements.sort_values("timestamp").reset_index(drop=True).copy()
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.weekday

    slot_history: dict[tuple[int, int], list[float]] = defaultdict(list)
    global_history: list[float] = []

    means: list[float | None] = []
    stdevs: list[float | None] = []
    counts: list[int] = []
    states: list[str] = []

    for row in df.itertuples():
        slot_key = (row.hour, row.weekday)
        slot_window = slot_history[slot_key][-ROLLING_WINDOW_SLOTS:]

        if len(slot_window) >= MIN_SAMPLES_SUFFICIENT:
            mean = statistics.mean(slot_window)
            stdev = statistics.pstdev(slot_window) if len(slot_window) > 1 else 0.0
            means.append(mean)
            stdevs.append(stdev)
            counts.append(len(slot_window))
            states.append(BaselineState.SUFFICIENT.value)
        elif len(global_history) >= GLOBAL_FALLBACK_MIN_SAMPLES:
            global_window = global_history[-GLOBAL_FALLBACK_WINDOW:]
            mean = statistics.mean(global_window)
            stdev = statistics.pstdev(global_window) if len(global_window) > 1 else 0.0
            means.append(mean)
            stdevs.append(stdev)
            counts.append(len(global_window))
            states.append(BaselineState.LIMITED.value)
        else:
            means.append(None)
            stdevs.append(None)
            counts.append(len(slot_window))
            states.append(BaselineState.NO_HISTORY.value)

        slot_history[slot_key].append(row.consumption)
        global_history.append(row.consumption)

    df["baseline_mean"] = means
    df["baseline_stddev"] = stdevs
    df["baseline_sample_count"] = counts
    df["baseline_state"] = states
    return df


def latest_slot_baselines(df_with_baselines: pd.DataFrame) -> list[dict]:
    """
    Extract one "current" baseline snapshot per (hour, weekday) slot — the
    baseline as of the most recent measurement in each slot — suitable for
    persisting into the `baselines` table (docs/DATA_MODEL.md) for fast
    lookup/display, independent of the causal per-row baselines used
    internally for anomaly scanning.
    """
    usable = df_with_baselines[df_with_baselines["baseline_state"] != BaselineState.NO_HISTORY.value]
    if usable.empty:
        return []
    latest_per_slot = usable.sort_values("timestamp").groupby(["hour", "weekday"], as_index=False).last()
    return [
        {
            "hour_of_day": int(row.hour),
            "day_of_week": int(row.weekday),
            "mean": float(row.baseline_mean),
            "stddev": float(row.baseline_stddev),
            "sample_count": int(row.baseline_sample_count),
            "state": row.baseline_state,
        }
        for row in latest_per_slot.itertuples()
    ]
