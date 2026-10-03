"""Response/request schemas for locations, resources, and measurements (docs/API.md)."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LocationOut(BaseModel):
    id: UUID
    name: str
    timezone: str
    operating_hours: dict

    model_config = {"from_attributes": True}


class ResourceOut(BaseModel):
    id: UUID
    location_id: UUID
    resource_type: str
    unit: str

    model_config = {"from_attributes": True}


class MeasurementOut(BaseModel):
    id: int
    resource_id: UUID
    timestamp: datetime
    consumption: float
    occupancy: int | None
    operating_status: str
    source: str
    scenario: str | None

    model_config = {"from_attributes": True}


class PaginatedMeasurements(BaseModel):
    items: list[MeasurementOut]
    total: int
    limit: int
    offset: int


class CSVUploadResponse(BaseModel):
    inserted: int
    skipped_duplicates: int
    locations_created: list[str]
    resources_created: int


class SimulateRequest(BaseModel):
    scenario: str = Field(description="One of the named scenarios, e.g. 'water_leak'.")
    location_name: str = Field(default="Greenfield Public School")
    seed: int | None = Field(default=None, description="Override the default deterministic seed.")
    weeks: int | None = Field(default=None, description="Override the default number of weeks generated.")


class SimulateResponse(BaseModel):
    scenario: str
    location_id: UUID
    location_name: str
    inserted: dict[str, int]
    skipped_duplicates: dict[str, int]
    period_start: date
    period_end: date


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class LiveTickRequest(BaseModel):
    location_id: UUID
    hours: int = Field(default=1, ge=1, le=24)
    seed: int = Field(default=42)


class LiveTickResponse(BaseModel):
    location_id: UUID
    location_name: str
    inserted: int
    simulated_start: datetime
    simulated_end: datetime
    resources: dict[str, int]
