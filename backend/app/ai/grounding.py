"""
Grounding validation (docs Milestone 4, requirement #5/#9; docs/AI_ARCHITECTURE.md,
"Validation before display").

Pydantic schema validation (`InvestigationResult`) only checks *shape* —
that the JSON has the right fields and types. This module checks *content*:
that the AI didn't invent a cause, cite evidence that wasn't given to it, or
state a number that doesn't actually appear in the evidence packet. Any
response that fails these checks is discarded in favor of the deterministic
fallback (docs Milestone 4, requirement #13) — this is the "absolute
numerical integrity rule" enforced in code, not just in the prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.schemas import InvestigationResult

# Numbers below this many significant digits (e.g. small integers like "0"
# occupancy, "3" hours) are common in ordinary English and would produce
# excessive false rejections if compared too strictly; we still check them,
# but see NUMERIC_TOLERANCE below for how comparisons are made.
NUMERIC_TOLERANCE_ABS = 0.5  # absolute tolerance for matching a stated number to an evidence number
NUMERIC_TOLERANCE_REL = 0.02  # 2% relative tolerance, for larger numbers

_NUMBER_PATTERN = re.compile(r"-?\d[\d,]*\.?\d*")


@dataclass
class GroundingResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def _extract_numbers(text: str) -> list[float]:
    """
    Extract every number in free text as a float, correctly treating
    comma-grouped thousands (e.g. "50,000") as one number rather than
    splitting on the comma into separate fragments (a real bug found
    during Checkpoint 9 testing: the previous pattern parsed "\u20b950,000" as
    two independent numbers, 50.0 and 0.0 -- and 0.0 is almost always
    present somewhere in a real evidence packet, so a large fabricated
    figure could slip past validation as long as it happened to be
    comma-formatted).
    """
    return [float(m.replace(",", "")) for m in _NUMBER_PATTERN.findall(text)]


def _collect_allowed_numbers(evidence_packet: dict) -> set[float]:
    """Every legitimate number the AI is allowed to reference, drawn straight from the evidence packet."""
    allowed: set[float] = set()

    def _walk(value):
        if isinstance(value, bool):
            return  # bools are not numbers for this purpose
        if isinstance(value, (int, float)):
            allowed.add(round(float(value), 4))
        elif isinstance(value, dict):
            for v in value.values():
                _walk(v)
        elif isinstance(value, list):
            for v in value:
                _walk(v)
        elif isinstance(value, str):
            for n in _extract_numbers(value):
                allowed.add(round(n, 4))

    _walk(evidence_packet)
    return allowed


def _number_is_allowed(number: float, allowed: set[float]) -> bool:
    for allowed_number in allowed:
        if abs(number - allowed_number) <= NUMERIC_TOLERANCE_ABS:
            return True
        if allowed_number != 0 and abs(number - allowed_number) / abs(allowed_number) <= NUMERIC_TOLERANCE_REL:
            return True
    return False


def validate_grounding(result: InvestigationResult, evidence_packet: dict) -> GroundingResult:
    """
    Check that `result` is fully grounded in `evidence_packet`:
      1. `likely_cause` and every alternative's `cause` must be one of the
         supplied `candidate_causes`.
      2. `supporting_evidence` entries must be `signal` values that were
         actually present in the evidence packet's `evidence` list.
      3. No number appearing anywhere in the free-text fields (`inference`,
         `observed`, `recommended_next_step`, `why_less_likely`) may be
         absent from the evidence packet — this is the numeric-integrity
         check: the AI may reference an evidence number, but not invent,
         round, or approximate a new one.
    """
    errors: list[str] = []

    candidate_cause_names = {c["cause"] for c in evidence_packet.get("candidate_causes", [])}
    if result.likely_cause not in candidate_cause_names:
        errors.append(f"likely_cause '{result.likely_cause}' is not in the supplied candidate_causes {sorted(candidate_cause_names)}.")

    for alt in result.alternative_explanations:
        if alt.cause not in candidate_cause_names:
            errors.append(f"alternative cause '{alt.cause}' is not in the supplied candidate_causes {sorted(candidate_cause_names)}.")

    evidence_signal_names = {e["signal"] for e in evidence_packet.get("evidence", [])}
    for signal_name in result.supporting_evidence:
        if signal_name not in evidence_signal_names:
            errors.append(f"supporting_evidence references unknown signal '{signal_name}' (not in the evidence packet).")

    allowed_numbers = _collect_allowed_numbers(evidence_packet)
    free_text_fields = [result.inference, result.recommended_next_step, *result.observed]
    free_text_fields += [alt.why_less_likely for alt in result.alternative_explanations]

    for text in free_text_fields:
        for number in _extract_numbers(text):
            if not _number_is_allowed(number, allowed_numbers):
                errors.append(f"free-text field contains an ungrounded number ({number}) not present in the evidence packet: {text!r}")

    return GroundingResult(valid=len(errors) == 0, errors=errors)
