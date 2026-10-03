"""Response/request schemas for analytics endpoints (docs/API.md)."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class RunAnalysisRequest(BaseModel):
    location_id: UUID


class ResourceAnalysisSummaryOut(BaseModel):
    resource_type: str
    total_anomalies: int
    by_severity: dict[str, int]
    operationally_suspicious: int


class BaselineOut(BaseModel):
    hour_of_day: int
    day_of_week: int
    mean: float
    stddev: float
    sample_count: int

    model_config = {"from_attributes": True}


class RunAnalysisResponse(BaseModel):
    location_id: UUID
    location_name: str
    resources: list[ResourceAnalysisSummaryOut]


class AnomalyOut(BaseModel):
    id: UUID
    resource_id: UUID
    detected_at: datetime
    window_start: datetime
    window_end: datetime
    severity: str
    classification: str
    deviation_pct: float | None
    z_score: float
    status: str

    model_config = {"from_attributes": True}


class AnomalyDetailOut(AnomalyOut):
    signals: dict
    evidence: list[dict]
    investigation: "InvestigationOut | None" = None


class InvestigationOut(BaseModel):
    id: UUID
    candidate_causes: list[dict]
    top_cause: str | None
    explanation: dict | None
    explanation_source: str | None
    recommendation: "RecommendationOut | None" = None

    model_config = {"from_attributes": True}


from app.schemas.intervention import RecommendationOut  # noqa: E402

InvestigationOut.model_rebuild()


class CostFactorOut(BaseModel):
    id: UUID
    resource_type: str
    rate: float
    currency: str
    effective_from: date

    model_config = {"from_attributes": True}


class EmissionFactorOut(BaseModel):
    id: UUID
    resource_type: str
    factor_value: float
    unit: str
    source: str
    version: str
    effective_from: date

    model_config = {"from_attributes": True}


class FactorsOut(BaseModel):
    cost_factors: list[CostFactorOut]
    emission_factors: list[EmissionFactorOut]


class UpdateCostFactorRequest(BaseModel):
    rate: float


class UpdateEmissionFactorRequest(BaseModel):
    factor_value: float
    source: str | None = None
    version: str | None = None
