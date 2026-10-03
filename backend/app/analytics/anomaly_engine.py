"""
Anomaly Engine — orchestrates the full deterministic pipeline for one
resource's telemetry (docs/ARCHITECTURE.md pipeline diagram: Data ->
Baseline -> Anomaly -> Evidence -> Investigation candidate causes).

Deliberately a pure function of its inputs (a measurements DataFrame, plus
optionally the other resource's flagged windows for cross-resource
correlation) with no database access — this is what makes it independently
unit-testable against the Milestone 2 scenario generators, and is the
"prove EcoTwin can understand the numerical state of a building before an
LLM ever sees it" deliverable for this milestone (docs Milestone 3, #20).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.analytics.baseline_engine import BaselineState, compute_causal_baselines, latest_slot_baselines
from app.analytics.candidate_causes import generate_candidate_causes
from app.analytics.config import Z_THRESHOLD_SUFFICIENT
from app.analytics.deviation import compute_deviation
from app.analytics.evidence import build_evidence
from app.analytics.persistence import FlaggedWindow, merge_flagged_windows
from app.analytics.severity import ContextSignals, SeverityResult, score_anomaly
from app.models.measurement import OperatingStatus
from app.models.resource import ResourceType


@dataclass
class AnomalyResult:
    resource_type: ResourceType
    window_start: datetime
    window_end: datetime
    severity: str
    classification: str
    deviation_pct: float | None
    z_score: float
    persistence_count: int
    signals: dict  # full raw signal packet, persisted verbatim on the Anomaly row
    evidence: list[dict]
    candidate_causes: list[dict]


def _majority(bool_series: pd.Series) -> bool:
    if len(bool_series) == 0:
        return False
    return bool(bool_series.mean() >= 0.5)


def analyze_resource(
    measurements: pd.DataFrame,
    resource_type: ResourceType,
    *,
    other_resource_flagged_windows: list[tuple[datetime, datetime]] | None = None,
) -> tuple[pd.DataFrame, list[AnomalyResult], list[dict]]:
    """
    Run the full deterministic pipeline for one resource.

    `measurements` must have columns: timestamp, consumption, occupancy,
    operating_status (as `OperatingStatus` values or their `.value` strings).

    Returns:
        (df_with_baselines, anomaly_results, current_baseline_snapshots)
    """
    other_windows = other_resource_flagged_windows or []

    df = measurements.sort_values("timestamp").reset_index(drop=True).copy()
    if not pd.api.types.is_string_dtype(df["operating_status"]):
        df["operating_status"] = df["operating_status"].apply(
            lambda s: s.value if isinstance(s, OperatingStatus) else s
        )

    df = compute_causal_baselines(df)

    z_scores = []
    deviation_pcts = []
    flagged = []
    for row in df.itertuples():
        if row.baseline_state == BaselineState.NO_HISTORY.value:
            z_scores.append(None)
            deviation_pcts.append(None)
            flagged.append(False)
            continue

        result = compute_deviation(row.consumption, row.baseline_mean, row.baseline_stddev, resource_type)
        z_scores.append(result.z_score)
        deviation_pcts.append(result.deviation_pct)

        if row.baseline_state == BaselineState.SUFFICIENT.value:
            flagged.append(abs(result.z_score) >= Z_THRESHOLD_SUFFICIENT)
        else:
            # "limited" state falls back to a resource-wide baseline that
            # blends all hours together (see baseline_engine.py). For a
            # resource with a strong diurnal swing (e.g. electricity
            # between closed-hours standby and daytime peak), that blended
            # baseline is a poor predictor for any single hour and would
            # otherwise flood the early "cold start" period with spurious
            # flags purely because we don't yet have slot-specific history
            # — not because anything is actually wrong. Per
            # ANOMALY_DETECTION.md's cold-start intent ("no anomaly is
            # raised" without enough comparable history), a `limited`
            # baseline is still computed and shown (e.g. for the Resources
            # page), but does not by itself flag an anomaly.
            flagged.append(False)

    df["z_score"] = z_scores
    df["deviation_pct"] = deviation_pcts
    df["flagged"] = flagged

    windows = merge_flagged_windows(df, flagged_column="flagged")

    anomaly_results = [_build_anomaly_result(df, w, resource_type, other_windows) for w in windows]
    baseline_snapshots = latest_slot_baselines(df)

    return df, anomaly_results, baseline_snapshots


def _build_anomaly_result(
    df: pd.DataFrame,
    window: FlaggedWindow,
    resource_type: ResourceType,
    other_resource_flagged_windows: list[tuple[datetime, datetime]],
) -> AnomalyResult:
    window_df = df.loc[window.row_indices]

    max_abs_z = window_df["z_score"].abs().max()
    # Representative deviation_pct for the window: mean of the rows where a
    # percentage was meaningful (see deviation.py); None if none were.
    valid_pcts = window_df["deviation_pct"].dropna()
    representative_pct = float(valid_pcts.mean()) if len(valid_pcts) > 0 else None

    majority_closed = _majority(window_df["operating_status"] == OperatingStatus.CLOSED.value)
    # Missing occupancy is genuinely unknown, not zero — filling with a
    # non-zero placeholder (1) before comparing to 0 means "unknown"
    # correctly never counts as "confirmed zero occupancy" evidence.
    # `pd.to_numeric` first ensures a numeric dtype so `fillna` doesn't
    # trigger a pandas object-dtype downcasting FutureWarning.
    majority_zero_occupancy = _majority(pd.to_numeric(window_df["occupancy"], errors="coerce").fillna(1) == 0)

    cross_resource_correlated = any(
        other_start < window.end and other_end > window.start
        for other_start, other_end in other_resource_flagged_windows
    )

    context = ContextSignals(
        max_abs_z_score=float(max_abs_z),
        persistence_count=window.persistence_count,
        majority_closed=majority_closed,
        majority_zero_occupancy=majority_zero_occupancy,
        cross_resource_correlated=cross_resource_correlated,
    )
    severity_result: SeverityResult = score_anomaly(context)

    persistence_hours = (window.end - window.start).total_seconds() / 3600

    evidence = build_evidence(
        deviation_pct=representative_pct,
        z_score=float(window_df["z_score"].iloc[window_df["z_score"].abs().argmax()]),
        persistence_count=window.persistence_count,
        persistence_hours=persistence_hours,
        context=context,
        classification=severity_result.classification.value,
    )

    candidate_causes = generate_candidate_causes(resource_type, context)

    signals = {
        "max_abs_z_score": float(max_abs_z),
        "deviation_pct": representative_pct,
        "persistence_count": window.persistence_count,
        "persistence_hours": persistence_hours,
        "majority_closed": majority_closed,
        "majority_zero_occupancy": majority_zero_occupancy,
        "cross_resource_correlated": cross_resource_correlated,
        # Raw consumption/baseline values, added for Milestone 4's AI
        # evidence packet (docs Milestone 4, requirement #3, "deterministic
        # metrics": actual/expected consumption) — averaged across the
        # window since a window can span several readings.
        "actual_consumption_mean": float(window_df["consumption"].mean()),
        "expected_consumption_mean": float(window_df["baseline_mean"].mean()),
        "baseline_stddev_used": float(window_df["baseline_stddev"].mean()),
        "baseline_sample_count": int(window_df["baseline_sample_count"].max()),
        "baseline_state": str(window_df["baseline_state"].iloc[0]),
        "scoring": {
            "deviation_points": severity_result.deviation_points,
            "persistence_points": severity_result.persistence_points,
            "context_points": severity_result.context_points,
            "total_points": severity_result.total_points,
            "context_signals_present": severity_result.context_signals_present,
        },
    }

    return AnomalyResult(
        resource_type=resource_type,
        window_start=window.start,
        window_end=window.end,
        severity=severity_result.severity.value,
        classification=severity_result.classification.value,
        deviation_pct=representative_pct,
        z_score=float(max_abs_z),
        persistence_count=window.persistence_count,
        signals=signals,
        evidence=evidence,
        candidate_causes=candidate_causes,
    )
