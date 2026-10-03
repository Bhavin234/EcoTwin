"""
Investigation API route (docs/API.md, docs Milestone 4, requirement #18).

Deliberately thin: all orchestration lives in
`app.ai.investigation_service.investigate_anomaly` — this route only wires
HTTP concerns (request/response schemas, status codes) around it.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.investigation_service import investigate_anomaly
from app.core.database import get_db
from app.schemas.investigation import InvestigateRequest, InvestigateResponse

router = APIRouter(tags=["investigation"])


@router.post("/anomalies/{anomaly_id}/investigate", response_model=InvestigateResponse)
def investigate(anomaly_id: UUID, request: InvestigateRequest = Body(default=InvestigateRequest()), db: Session = Depends(get_db)):
    try:
        outcome = investigate_anomaly(db, anomaly_id, force=request.force)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message else 422
        code = "anomaly_not_found" if status_code == 404 else "investigation_not_applicable"
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message}) from exc

    return InvestigateResponse(
        anomaly_id=anomaly_id,
        investigation_id=outcome.investigation.id,
        explanation_source=outcome.source,
        result=outcome.result,
        fallback_reason=outcome.fallback_reason,
    )
