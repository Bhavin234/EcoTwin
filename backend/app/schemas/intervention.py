"""Request/response schemas for recommendation/intervention/verification/impact endpoints (docs/API.md)."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: UUID
    investigation_id: UUID
    action_text: str
    priority: str
    estimated_saving: float | None
    intervention: "InterventionOut | None" = None

    model_config = {"from_attributes": True}


class InterventionOut(BaseModel):
    id: UUID
    recommendation_id: UUID
    status: str
    verification_status: str
    marked_complete_at: datetime | None

    model_config = {"from_attributes": True}


class CompleteInterventionRequest(BaseModel):
    completed_at: datetime | None = None


class VerifyInterventionResponse(BaseModel):
    intervention_id: UUID
    verification_status: str
    window_start: datetime | None
    window_end: datetime | None
    actual_post_consumption_mean: float | None
    ordinary_baseline_mean: float | None
    ordinary_baseline_state: str | None
    counterfactual_rate: float | None
    avoided_consumption: float | None
    money_saved: float | None
    co2e_avoided_kg: float | None
    message: str


class ImpactRecordOut(BaseModel):
    id: UUID
    kind: str
    resource_id: UUID | None
    anomaly_id: UUID | None
    intervention_id: UUID | None
    water_saved: float | None
    energy_saved: float | None
    co2e_avoided_kg: float
    money_saved: float
    window_start: datetime | None
    window_end: datetime | None
    emission_factor_version: str | None
    cost_factor_currency: str | None

    model_config = {"from_attributes": True}


class ImpactSummaryOut(BaseModel):
    kind: str
    total_money_saved: float
    total_co2e_avoided_kg: float
    total_water_saved: float
    total_energy_saved: float
    record_count: int


class ImpactResponse(BaseModel):
    summary: list[ImpactSummaryOut]
    records: list[ImpactRecordOut]


class DemoResultOut(BaseModel):
    status: str
    location_id: UUID | None
    location_name: str
    anomaly_id: UUID | None = None
    resource_type: str | None = None
    severity: str | None = None
    explanation_source: str | None = None
    likely_cause: str | None = None
    deviation_pct: float | None = None
    z_score: float | None = None
    persistence_hours: float | None = None
    majority_closed: bool | None = None
    majority_zero_occupancy: bool | None = None
    recommendation_text: str | None = None
    intervention_id: UUID | None = None
    verification_status: str | None = None
    avoided_consumption: float | None = None
    money_saved: float | None = None
    co2e_avoided_kg: float | None = None
    message: str


class RunDemoRequest(BaseModel):
    scenario: str = "post_intervention_recovery"
    location_name: str = "Greenfield Public School"


class ResetDemoRequest(BaseModel):
    location_name: str = "Greenfield Public School"


class ResetDemoResponse(BaseModel):
    reset: bool
    location_name: str
