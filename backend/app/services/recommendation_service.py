"""
Recommendation service (docs Milestone 5, requirements #3-5).

A Recommendation is created (or updated) automatically once an
investigation finishes — see the call from
`app.ai.investigation_service.investigate_anomaly` — rather than being a
separate manual step, per the workflow diagram in the brief:
`Anomaly -> Investigation -> Recommended Action`.

`action_text` is allowed to come from the AI/fallback investigation's
`recommended_next_step` (reasoning is AI's job). `priority` and
`estimated_saving` are always computed deterministically here — the AI is
never involved in either (docs Milestone 5, requirement #5, "do not let AI
invent savings").
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.calculations import calculate_co2e, calculate_cost, compute_savings_foundation
from app.models.anomaly import Anomaly, Severity
from app.models.impact import ImpactKind, ImpactRecord
from app.models.investigation import Investigation
from app.models.recommendation import Priority, Recommendation
from app.models.resource import Resource, ResourceType
from app.services.factor_service import ensure_default_factors, get_active_cost_factor, get_active_emission_factor

_PRIORITY_BY_SEVERITY = {
    Severity.CRITICAL: Priority.HIGH,
    Severity.HIGH: Priority.HIGH,
    Severity.MEDIUM: Priority.MEDIUM,
    Severity.LOW: Priority.LOW,
}


def _priority_from_severity(severity: Severity) -> Priority:
    return _PRIORITY_BY_SEVERITY.get(severity, Priority.MEDIUM)


def _estimated_wastage(anomaly: Anomaly) -> float:
    """
    Total excess consumption (native unit) over the anomaly's own observed
    window — deliberately *not* annualized or projected forward (docs
    Milestone 5, requirement #18: "do not present an annualized estimate
    as if it were verified savings"; this keeps the number exactly what it
    claims to be: the wastage actually observed during this window).
    """
    signals = anomaly.signals
    foundation = compute_savings_foundation(
        expected_consumption=signals.get("expected_consumption_mean", 0.0),
        actual_consumption=signals.get("actual_consumption_mean", 0.0),
    )
    persistence_count = signals.get("persistence_count", 1)
    return foundation.excess_consumption * persistence_count


def create_or_update_recommendation(db: Session, investigation: Investigation, anomaly: Anomaly, action_text: str) -> Recommendation:
    """
    Create (or, if one already exists for this investigation, update) the
    Recommendation row, and (re)create its associated `estimated`
    ImpactRecord — both fully deterministic aside from `action_text`.
    """
    ensure_default_factors(db)

    existing = db.query(Recommendation).filter(Recommendation.investigation_id == investigation.id).first()
    priority = _priority_from_severity(anomaly.severity)
    estimated_wastage = _estimated_wastage(anomaly)

    if existing is not None:
        existing.action_text = action_text
        existing.priority = priority
        existing.estimated_saving = estimated_wastage
        recommendation = existing
    else:
        recommendation = Recommendation(
            investigation_id=investigation.id,
            action_text=action_text,
            priority=priority,
            estimated_saving=estimated_wastage,
        )
        db.add(recommendation)

    db.flush()

    _create_or_replace_estimated_impact_record(db, anomaly, estimated_wastage)

    db.commit()
    db.refresh(recommendation)
    return recommendation


def _create_or_replace_estimated_impact_record(db: Session, anomaly: Anomaly, estimated_wastage: float) -> ImpactRecord:
    resource = db.get(Resource, anomaly.resource_id)

    # Replace any previous estimate for this anomaly (e.g. if the
    # investigation was re-run with force=True) rather than accumulating
    # duplicates — this mirrors the "full re-analysis" idempotency pattern
    # already used by app.services.analytics_service.
    db.query(ImpactRecord).filter(ImpactRecord.anomaly_id == anomaly.id, ImpactRecord.kind == ImpactKind.ESTIMATED).delete()

    cost_factor = get_active_cost_factor(db, resource.resource_type)
    emission_factor = get_active_emission_factor(db, resource.resource_type)

    money_saved = calculate_cost(estimated_wastage, cost_factor) if cost_factor else 0.0
    co2e_avoided = calculate_co2e(estimated_wastage, emission_factor) if emission_factor else 0.0

    record = ImpactRecord(
        anomaly_id=anomaly.id,
        resource_id=resource.id,
        intervention_id=None,
        kind=ImpactKind.ESTIMATED,
        water_saved=estimated_wastage if resource.resource_type == ResourceType.WATER else None,
        energy_saved=estimated_wastage if resource.resource_type == ResourceType.ELECTRICITY else None,
        co2e_avoided_kg=co2e_avoided,
        money_saved=money_saved,
        window_start=anomaly.window_start,
        window_end=anomaly.window_end,
        emission_factor_value_used=emission_factor.factor_value if emission_factor else None,
        emission_factor_version=emission_factor.version if emission_factor else None,
        emission_factor_source=emission_factor.source if emission_factor else None,
        cost_factor_rate_used=cost_factor.rate if cost_factor else None,
        cost_factor_currency=cost_factor.currency if cost_factor else None,
    )
    db.add(record)
    db.flush()
    return record
