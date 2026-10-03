"""
AI output contract (docs Milestone 4, requirement #4).

`InvestigationResult` is the one shape produced by *either* the AI
Reasoning Layer or the deterministic fallback engine — the rest of the
application (API, persistence) never needs to know which one produced a
given result; only `explanation_source` on the `Investigation` row records
that.

Note the deliberate separation of confidence concepts:
  - `reasoning_confidence` is the AI's own qualitative assessment of how
    strongly the evidence supports its conclusion — categorical
    (high/medium/low) by design, never a fabricated percentage
    (docs Milestone 4, requirement #4).
  - The *deterministic* confidence for each candidate cause
    (`high`/`medium`/`low`, from `app.analytics.candidate_causes`) is a
    separate, backend-computed value and is not something this schema
    re-derives or overrides.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReasoningConfidence = Literal["high", "medium", "low"]


class AlternativeExplanation(BaseModel):
    cause: str
    why_less_likely: str = Field(description="Brief reason this cause is less consistent with the evidence than the likely cause.")


class InvestigationResult(BaseModel):
    """
    The structured investigation output (docs Milestone 4, requirement #4/#16).

    `observed` and `inference` implement the "distinguish observation from
    inference" requirement: `observed` restates only facts that are
    literally present in the evidence packet, `inference` is the reasoning
    that connects those facts to `likely_cause`.
    """

    likely_cause: str = Field(description="Must be one of the candidate_causes provided in the evidence packet.")
    observed: list[str] = Field(description="Objective facts drawn directly from the evidence packet, not interpretation.")
    inference: str = Field(description="The reasoning connecting the observed facts to the likely cause.")
    supporting_evidence: list[str] = Field(
        description="Evidence signal names (e.g. 'baseline_deviation', 'occupancy') from the evidence packet that support the conclusion."
    )
    alternative_explanations: list[AlternativeExplanation] = Field(
        description="Other candidate causes from the evidence packet, and why each is less likely than likely_cause."
    )
    recommended_next_step: str = Field(description="A concrete investigative action, not a quantified savings estimate.")
    reasoning_confidence: ReasoningConfidence
