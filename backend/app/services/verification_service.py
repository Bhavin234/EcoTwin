"""
Verification service (docs Milestone 5, requirements #8-13, #16, #19).

Reuses the Milestone 3 baseline/deviation engine exactly — no second
baseline methodology (requirement #9) — and answers two distinct
questions with two distinct comparisons:

1. **"Does this look normal again?"** — actual post-intervention
   consumption compared against the ordinary contextual baseline (the same
   causal, cold-start-aware engine from `app.analytics.baseline_engine`
   and `app.analytics.deviation`). This drives `verification_status`.

2. **"How much did we avoid?"** — actual post-intervention consumption
   compared against the *counterfactual*: the anomalous rate that was
   actually observed during the original anomaly window (i.e., what
   consumption would likely have continued to be without the fix). This
   drives the avoided-consumption / cost / CO2e numbers.

These are different comparisons on purpose. A naive single comparison
(post-actual vs. ordinary baseline) would make "avoided consumption"
collapse to ~0 once a leak is fixed — which is true but useless as an
impact figure; what a user actually wants to know is how much waste was
avoided relative to the problem continuing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.baseline_engine import BaselineState, compute_causal_baselines
from app.analytics.calculations import calculate_co2e, calculate_cost, compute_savings_foundation
from app.analytics.config import Z_THRESHOLD_SUFFICIENT
from app.analytics.deviation import compute_deviation
from app.models.anomaly import Anomaly
from app.models.impact import ImpactKind, ImpactRecord
from app.models.intervention import Intervention, InterventionStatus, VerificationStatus
from app.models.measurement import Measurement, OperatingStatus
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.services.factor_service import get_active_cost_factor, get_active_emission_factor

# How long a post-intervention window we look at. Bounded below by the
# original anomaly's own persistence (a fair, like-for-like comparison
# length) and above by a fixed cap, so verification doesn't wait
# indefinitely for a slow-moving resource.
MIN_VERIFICATION_WINDOW_HOURS = 3
MAX_VERIFICATION_WINDOW_HOURS = 24

# Below this many post-intervention measurements, we don't have enough to
# say anything meaningful yet.
MIN_VERIFICATION_SAMPLES = 2


@dataclass
class VerificationOutcome:
    intervention: Intervention
    verification_status: str
    window_start: datetime | None
    window_end: datetime | None
    actual_post_consumption_mean: float | None
    ordinary_baseline_mean: float | None
    ordinary_baseline_state: str | None
    counterfactual_rate: float | None  # the anomalous rate being compared against for avoided-consumption
    avoided_consumption: float | None
    money_saved: float | None
    co2e_avoided_kg: float | None
    message: str


def _verification_window(intervention: Intervention, anomaly: Anomaly) -> tuple[datetime, datetime]:
    persistence_hours = anomaly.signals.get("persistence_hours", MIN_VERIFICATION_WINDOW_HOURS)
    window_hours = min(max(persistence_hours, MIN_VERIFICATION_WINDOW_HOURS), MAX_VERIFICATION_WINDOW_HOURS)
    start = intervention.marked_complete_at
    end = start + timedelta(hours=window_hours)
    return start, end


def verify_intervention(db: Session, intervention_id: UUID) -> VerificationOutcome:
    """
    Run (and persist) verification for one completed intervention. Safe to
    call repeatedly — always recomputes from current telemetry rather than
    caching, since new measurements may have arrived; any previous
    `verified`/`estimated` ImpactRecord tied to this intervention is
    replaced, not duplicated.
    """
    intervention = db.get(Intervention, intervention_id)
    if intervention is None:
        raise ValueError(f"Intervention {intervention_id} not found")
    if intervention.status != InterventionStatus.COMPLETED or intervention.marked_complete_at is None:
        raise ValueError(f"Intervention {intervention_id} is not completed yet — nothing to verify.")

    recommendation = db.get(Recommendation, intervention.recommendation_id)
    investigation = recommendation.investigation
    anomaly = investigation.anomaly
    resource = db.get(Resource, anomaly.resource_id)

    window_start, window_end = _verification_window(intervention, anomaly)

    rows = db.execute(
        select(Measurement.timestamp, Measurement.consumption, Measurement.occupancy, Measurement.operating_status).where(
            Measurement.resource_id == resource.id
        )
    ).all()
    full_df = pd.DataFrame(rows, columns=["timestamp", "consumption", "occupancy", "operating_status"])
    full_df["operating_status"] = full_df["operating_status"].apply(
        lambda s: s.value if isinstance(s, OperatingStatus) else s
    )

    post_df = full_df[(full_df["timestamp"] >= window_start) & (full_df["timestamp"] < window_end)]

    if len(post_df) < MIN_VERIFICATION_SAMPLES:
        return _finalize(
            db, intervention, VerificationStatus.INSUFFICIENT_DATA, window_start, window_end,
            message=f"Only {len(post_df)} measurement(s) available in the verification window so far; need at least {MIN_VERIFICATION_SAMPLES}.",
        )

    # Baseline lookup: run the identical causal engine from Milestone 3
    # over the full history (which now legitimately includes the anomaly
    # itself as past data) and read off the baseline computed for exactly
    # the post-intervention rows.
    baselined = compute_causal_baselines(full_df)
    post_baselined = baselined[(baselined["timestamp"] >= window_start) & (baselined["timestamp"] < window_end)]

    usable = post_baselined[post_baselined["baseline_state"] != BaselineState.NO_HISTORY.value]
    if usable.empty:
        return _finalize(
            db, intervention, VerificationStatus.INSUFFICIENT_DATA, window_start, window_end,
            message="No usable baseline exists yet for the post-intervention window's time slots.",
        )

    actual_post_mean = float(usable["consumption"].mean())
    ordinary_baseline_mean = float(usable["baseline_mean"].mean())
    ordinary_baseline_stddev = float(usable["baseline_stddev"].mean())
    # Conservative: if any row in the window falls back to a "limited"
    # baseline, treat the whole window as limited-confidence rather than
    # averaging away the uncertainty.
    baseline_state = (
        BaselineState.SUFFICIENT.value
        if (usable["baseline_state"] == BaselineState.SUFFICIENT.value).all()
        else BaselineState.LIMITED.value
    )

    deviation = compute_deviation(actual_post_mean, ordinary_baseline_mean, ordinary_baseline_stddev, resource.resource_type)

    # Contextual comparability check (docs Milestone 5, requirement #10):
    # only claim high-confidence verification if the operating
    # context of the verification window resembles the original anomaly
    # window (both closed/unoccupied, or neither) — otherwise a change in
    # context could explain the difference just as well as the fix did.
    anomaly_signals = anomaly.signals
    context_matches = (
        bool(anomaly_signals.get("majority_closed")) == bool((usable["operating_status"] == OperatingStatus.CLOSED.value).mean() >= 0.5)
        and bool(anomaly_signals.get("majority_zero_occupancy")) == bool((pd.to_numeric(usable["occupancy"], errors="coerce").fillna(1) == 0).mean() >= 0.5)
    )

    if deviation.z_score >= Z_THRESHOLD_SUFFICIENT:
        verification_status = VerificationStatus.NO_MEASURABLE_IMPROVEMENT
    elif baseline_state == BaselineState.SUFFICIENT.value and context_matches:
        verification_status = VerificationStatus.VERIFIED
    else:
        verification_status = VerificationStatus.IMPROVEMENT_DETECTED

    # Avoided consumption: actual post-intervention behavior compared
    # against the counterfactual of the anomaly continuing at its
    # originally observed rate (not against the ordinary baseline — see
    # module docstring).
    counterfactual_rate = anomaly_signals.get("actual_consumption_mean", actual_post_mean)
    foundation = compute_savings_foundation(expected_consumption=counterfactual_rate, actual_consumption=actual_post_mean)
    avoided_consumption = foundation.avoided_consumption * len(post_df)

    cost_factor = get_active_cost_factor(db, resource.resource_type)
    emission_factor = get_active_emission_factor(db, resource.resource_type)
    money_saved = calculate_cost(avoided_consumption, cost_factor) if cost_factor else 0.0
    co2e_avoided = calculate_co2e(avoided_consumption, emission_factor) if emission_factor else 0.0

    message = {
        VerificationStatus.NO_MEASURABLE_IMPROVEMENT: (
            f"Post-intervention consumption is still {deviation.z_score:.1f} standard deviations above the "
            "expected baseline — no measurable improvement yet."
        ),
        VerificationStatus.VERIFIED: (
            "Post-intervention consumption is back within the normal expected range, backed by a "
            "sufficient-confidence baseline and matching operating context."
        ),
        VerificationStatus.IMPROVEMENT_DETECTED: (
            "Post-intervention consumption looks roughly normal again, but with lower confidence "
            "(limited baseline history and/or a change in operating context during the comparison window)."
        ),
    }[verification_status]

    return _finalize(
        db,
        intervention,
        verification_status,
        window_start,
        window_end,
        actual_post_consumption_mean=actual_post_mean,
        ordinary_baseline_mean=ordinary_baseline_mean,
        ordinary_baseline_state=baseline_state,
        counterfactual_rate=counterfactual_rate,
        avoided_consumption=avoided_consumption,
        money_saved=money_saved,
        co2e_avoided_kg=co2e_avoided,
        message=message,
        resource=resource,
        anomaly=anomaly,
        cost_factor=cost_factor,
        emission_factor=emission_factor,
    )


def _finalize(
    db: Session,
    intervention: Intervention,
    verification_status: VerificationStatus,
    window_start: datetime,
    window_end: datetime,
    *,
    message: str,
    actual_post_consumption_mean: float | None = None,
    ordinary_baseline_mean: float | None = None,
    ordinary_baseline_state: str | None = None,
    counterfactual_rate: float | None = None,
    avoided_consumption: float | None = None,
    money_saved: float | None = None,
    co2e_avoided_kg: float | None = None,
    resource=None,
    anomaly=None,
    cost_factor=None,
    emission_factor=None,
) -> VerificationOutcome:
    intervention.verification_status = verification_status
    db.commit()
    db.refresh(intervention)

    # Only persist a formal ImpactRecord when there's something meaningful
    # to record — never for insufficient_data, and never mislabel a
    # lower-confidence `improvement_detected` result as `verified` (docs
    # Milestone 5, requirement #16: "do not mark something verified merely
    # because an intervention was completed").
    if verification_status in (VerificationStatus.VERIFIED, VerificationStatus.IMPROVEMENT_DETECTED, VerificationStatus.NO_MEASURABLE_IMPROVEMENT) and resource is not None:
        db.query(ImpactRecord).filter(ImpactRecord.intervention_id == intervention.id).delete()

        kind = ImpactKind.VERIFIED if verification_status == VerificationStatus.VERIFIED else ImpactKind.ESTIMATED
        record = ImpactRecord(
            intervention_id=intervention.id,
            anomaly_id=anomaly.id if anomaly else None,
            resource_id=resource.id,
            kind=kind,
            water_saved=avoided_consumption if resource.resource_type.value == "water" else None,
            energy_saved=avoided_consumption if resource.resource_type.value == "electricity" else None,
            co2e_avoided_kg=co2e_avoided_kg or 0.0,
            money_saved=money_saved or 0.0,
            window_start=window_start,
            window_end=window_end,
            emission_factor_value_used=emission_factor.factor_value if emission_factor else None,
            emission_factor_version=emission_factor.version if emission_factor else None,
            emission_factor_source=emission_factor.source if emission_factor else None,
            cost_factor_rate_used=cost_factor.rate if cost_factor else None,
            cost_factor_currency=cost_factor.currency if cost_factor else None,
        )
        db.add(record)
        db.commit()

    return VerificationOutcome(
        intervention=intervention,
        verification_status=verification_status.value,
        window_start=window_start,
        window_end=window_end,
        actual_post_consumption_mean=actual_post_consumption_mean,
        ordinary_baseline_mean=ordinary_baseline_mean,
        ordinary_baseline_state=ordinary_baseline_state,
        counterfactual_rate=counterfactual_rate,
        avoided_consumption=avoided_consumption,
        money_saved=money_saved,
        co2e_avoided_kg=co2e_avoided_kg,
        message=message,
    )
