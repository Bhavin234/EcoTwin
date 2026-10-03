"""Request/response schemas for the investigation endpoint (docs/API.md)."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.ai.schemas import InvestigationResult


class InvestigateRequest(BaseModel):
    force: bool = False


class InvestigateResponse(BaseModel):
    anomaly_id: UUID
    investigation_id: UUID
    explanation_source: str  # "ai" | "fallback"
    result: InvestigationResult
    fallback_reason: str | None = None
