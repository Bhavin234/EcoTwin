"""
Investigation service (docs Milestone 4, requirement #11/#18).

The single orchestration point: builds the evidence packet, calls the AI
(via an injectable provider so tests never need real network access or a
real API key), validates and grounds the response, falls back to the
deterministic engine on any failure, and persists the result onto the
existing `Investigation` row. Kept independent of FastAPI — the API route
in `app/api/investigation.py` just calls this.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.client import AIClientError, call_anthropic
from app.ai.evidence_packet import build_evidence_packet
from app.ai.fallback import build_fallback_investigation
from app.ai.grounding import validate_grounding
from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas import InvestigationResult
from app.models.anomaly import Anomaly, AnomalyClassification
from app.models.investigation import ExplanationSource, Investigation
from app.models.location import Location
from app.models.resource import Resource
from app.services.recommendation_service import create_or_update_recommendation

logger = logging.getLogger("ecotwin.ai")

AIProvider = Callable[[str, str], str]  # (system_prompt, user_prompt) -> raw response text


@dataclass
class InvestigationOutcome:
    investigation: Investigation
    result: InvestigationResult
    source: str  # "ai" | "fallback"
    fallback_reason: str | None = None


def _strip_markdown_fence(text: str) -> str:
    """Defensive cleanup in case the model wraps its JSON in ```json fences despite instructions."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]  # drop opening fence (with or without a language tag)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def _parse_and_validate_ai_response(raw_text: str, evidence_packet: dict) -> InvestigationResult:
    """Parse, schema-validate, and ground-validate a raw AI response. Raises ValueError on any failure."""
    cleaned = _strip_markdown_fence(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI response was not valid JSON: {exc}") from exc

    try:
        result = InvestigationResult.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"AI response did not match the required schema: {exc}") from exc

    grounding = validate_grounding(result, evidence_packet)
    if not grounding.valid:
        raise ValueError(f"AI response failed grounding validation: {grounding.errors}")

    return result


def investigate_anomaly(
    db: Session,
    anomaly_id: UUID,
    *,
    ai_provider: AIProvider | None = None,
    force: bool = False,
) -> InvestigationOutcome:
    """
    Run (or return the cached result of) an investigation for one anomaly.

    `ai_provider` defaults to the real Anthropic client
    (`app.ai.client.call_anthropic`); tests pass a stub here instead so no
    real network call or API key is required (docs Milestone 4,
    requirement #21). Repeated calls return the previously persisted
    result unless `force=True` (docs Milestone 4, requirement #18,
    "avoid repeated AI calls for the same investigation unless explicitly
    requested").
    """
    ai_provider = ai_provider or call_anthropic

    anomaly = db.get(Anomaly, anomaly_id)
    if anomaly is None:
        raise ValueError(f"Anomaly {anomaly_id} not found")
    if anomaly.classification != AnomalyClassification.OPERATIONALLY_SUSPICIOUS:
        raise ValueError(
            f"Anomaly {anomaly_id} is classified '{anomaly.classification.value}', not 'operationally_suspicious' "
            "— only operationally suspicious anomalies are promoted to a full investigation (see ANOMALY_DETECTION.md)."
        )

    investigation = anomaly.investigation
    if investigation is None:
        raise ValueError(f"Anomaly {anomaly_id} has no Investigation row (expected one from the analytics service).")

    if investigation.explanation is not None and not force:
        cached_result = InvestigationResult.model_validate(investigation.explanation)
        return InvestigationOutcome(investigation=investigation, result=cached_result, source=investigation.explanation_source.value)

    resource = db.get(Resource, anomaly.resource_id)
    location = db.get(Location, resource.location_id)
    evidence_packet = build_evidence_packet(anomaly, investigation, resource, location)

    result: InvestigationResult
    source: ExplanationSource
    fallback_reason: str | None = None

    try:
        raw_response = ai_provider(SYSTEM_PROMPT, build_user_prompt(evidence_packet))
        result = _parse_and_validate_ai_response(raw_response, evidence_packet)
        source = ExplanationSource.AI
    except AIClientError as exc:
        logger.info("AI investigation unavailable for anomaly %s, using fallback: %s", anomaly_id, exc)
        fallback_reason = str(exc)
        result = build_fallback_investigation(evidence_packet)
        source = ExplanationSource.FALLBACK
    except ValueError as exc:
        logger.warning("AI investigation response rejected for anomaly %s, using fallback: %s", anomaly_id, exc)
        fallback_reason = str(exc)
        result = build_fallback_investigation(evidence_packet)
        source = ExplanationSource.FALLBACK

    investigation.explanation = result.model_dump()
    investigation.explanation_source = source
    investigation.top_cause = result.likely_cause
    db.commit()
    db.refresh(investigation)

    # Milestone 5: a Recommendation (and its deterministic estimated
    # impact) is generated automatically as soon as an investigation
    # completes — see app/services/recommendation_service.py. action_text
    # may come from the AI/fallback reasoning; priority and the estimated
    # savings figure are always computed deterministically there.
    create_or_update_recommendation(db, investigation, anomaly, result.recommended_next_step)

    return InvestigationOutcome(investigation=investigation, result=result, source=source.value, fallback_reason=fallback_reason)
