"""
Analytics persistence service — the DB-facing layer around the pure
`app.analytics.anomaly_engine`. Loads measurements, runs the deterministic
pipeline per resource (feeding each resource the other's flagged windows
for cross-resource correlation), and persists Baseline / Anomaly /
Investigation rows (docs Milestone 3, requirement #16).

Only `operationally_suspicious` anomalies get an Investigation row with
candidate causes — `unusual` anomalies are still persisted (so the
Resources page can show them) but are not promoted to a full investigation
(docs/ANOMALY_DETECTION.md, "'Unusual' vs 'operationally suspicious'").
`Investigation.explanation` / `explanation_source` are left null here —
that's the AI Reasoning Layer's job in Milestone 4.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.anomaly_engine import AnomalyResult, analyze_resource
from app.models.anomaly import Anomaly, AnomalyClassification, Severity
from app.models.baseline import Baseline
from app.models.investigation import Investigation
from app.models.location import Location
from app.models.measurement import Measurement
from app.models.resource import Resource, ResourceType
from app.services.factor_service import ensure_default_factors


@dataclass
class ResourceAnalysisSummary:
    resource_type: str
    total_anomalies: int
    by_severity: dict[str, int]
    operationally_suspicious: int


@dataclass
class LocationAnalysisResult:
    location_id: UUID
    location_name: str
    resources: list[ResourceAnalysisSummary]


def _load_measurements_df(db: Session, resource_id: UUID) -> pd.DataFrame:
    rows = db.execute(
        select(
            Measurement.timestamp, Measurement.consumption, Measurement.occupancy, Measurement.operating_status
        ).where(Measurement.resource_id == resource_id)
    ).all()
    return pd.DataFrame(rows, columns=["timestamp", "consumption", "occupancy", "operating_status"])


def _persist_baselines(db: Session, resource_id: UUID, snapshots: list[dict]) -> None:
    # Clear any existing snapshot rows for this resource and replace them —
    # simpler and safer for the MVP than a per-slot upsert, since this
    # service always recomputes the full picture from scratch.
    db.query(Baseline).filter(Baseline.resource_id == resource_id).delete()
    for snap in snapshots:
        db.add(
            Baseline(
                resource_id=resource_id,
                hour_of_day=snap["hour_of_day"],
                day_of_week=snap["day_of_week"],
                mean=snap["mean"],
                stddev=snap["stddev"],
                sample_count=snap["sample_count"],
            )
        )


def _persist_anomalies(db: Session, resource_id: UUID, results: list[AnomalyResult]) -> None:
    # Same replace-in-full approach as baselines: this service treats each
    # run as a full re-analysis of the resource's available history.
    existing_ids = [a.id for a in db.query(Anomaly).filter(Anomaly.resource_id == resource_id).all()]
    if existing_ids:
        db.query(Investigation).filter(Investigation.anomaly_id.in_(existing_ids)).delete(synchronize_session=False)
        db.query(Anomaly).filter(Anomaly.resource_id == resource_id).delete(synchronize_session=False)

    for result in results:
        anomaly = Anomaly(
            resource_id=resource_id,
            detected_at=result.window_end,
            window_start=result.window_start,
            window_end=result.window_end,
            severity=Severity(result.severity),
            deviation_pct=result.deviation_pct,
            z_score=result.z_score,
            signals=result.signals,
            classification=AnomalyClassification(result.classification),
        )
        db.add(anomaly)
        db.flush()  # assign anomaly.id

        if result.classification == AnomalyClassification.OPERATIONALLY_SUSPICIOUS.value:
            investigation = Investigation(
                anomaly_id=anomaly.id,
                candidate_causes=result.candidate_causes,
                top_cause=result.candidate_causes[0]["cause"] if result.candidate_causes else None,
                explanation=None,  # Milestone 4: AI Reasoning Layer or its fallback fills this in
                explanation_source=None,
            )
            db.add(investigation)


def run_analysis_for_location(db: Session, location_id: UUID) -> LocationAnalysisResult:
    """
    Run the full deterministic pipeline for every resource at a location,
    persisting Baseline and Anomaly (+ Investigation, for
    operationally-suspicious anomalies) rows.
    """
    ensure_default_factors(db)

    location = db.get(Location, location_id)
    if location is None:
        raise ValueError(f"Location {location_id} not found")

    resources = db.query(Resource).filter(Resource.location_id == location_id).all()

    # First pass: analyze each resource independently to get its flagged
    # windows, so the second pass can check cross-resource correlation
    # symmetrically (each resource sees the other's windows).
    per_resource_data: dict[UUID, tuple[ResourceType, pd.DataFrame]] = {}
    for resource in resources:
        df = _load_measurements_df(db, resource.id)
        per_resource_data[resource.id] = (resource.resource_type, df)

    # Build preliminary flagged windows per resource (without cross-resource
    # correlation yet) purely to feed the second, final pass.
    preliminary_windows: dict[UUID, list[tuple[datetime, datetime]]] = {}
    for resource_id, (resource_type, df) in per_resource_data.items():
        if df.empty:
            preliminary_windows[resource_id] = []
            continue
        _, results, _ = analyze_resource(df, resource_type)
        preliminary_windows[resource_id] = [(r.window_start, r.window_end) for r in results]

    summaries: list[ResourceAnalysisSummary] = []
    for resource in resources:
        resource_type, df = per_resource_data[resource.id]
        if df.empty:
            summaries.append(
                ResourceAnalysisSummary(
                    resource_type=resource_type.value, total_anomalies=0, by_severity={}, operationally_suspicious=0
                )
            )
            continue

        other_windows: list[tuple[datetime, datetime]] = []
        for other_resource in resources:
            if other_resource.id != resource.id:
                other_windows.extend(preliminary_windows.get(other_resource.id, []))

        _, results, baseline_snapshots = analyze_resource(df, resource_type, other_resource_flagged_windows=other_windows)

        _persist_baselines(db, resource.id, baseline_snapshots)
        _persist_anomalies(db, resource.id, results)

        by_severity: dict[str, int] = {}
        for r in results:
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1

        summaries.append(
            ResourceAnalysisSummary(
                resource_type=resource_type.value,
                total_anomalies=len(results),
                by_severity=by_severity,
                operationally_suspicious=sum(1 for r in results if r.classification == "operationally_suspicious"),
            )
        )

    db.commit()

    return LocationAnalysisResult(location_id=location.id, location_name=location.name, resources=summaries)
