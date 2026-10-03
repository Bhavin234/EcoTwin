# AI Architecture (Revised)

## Principle

Numbers come from statistics. Reasoning comes from AI, but only over evidence the deterministic system already produced. The AI's job is upgraded from "phrase this nicely" to "reason over structured evidence and produce a structured, checkable explanation" — but it is still never the source of a number, a score, or a confidence percentage that drives the UI.

## What the AI sees

A structured evidence packet built entirely by the deterministic Evidence Builder and Investigation Engine — never raw, unfiltered telemetry, and never asked to compute anything itself. Example:

```json
{
  "resource": "water",
  "anomaly_severity": "HIGH",
  "deviation_pct": 238,
  "operating_status": "closed",
  "occupancy": 0,
  "duration_hours": 3,
  "pattern": "sustained_elevated",
  "candidate_causes": [
    {"cause": "plumbing_leak", "deterministic_score": "high"},
    {"cause": "irrigation_left_active", "deterministic_score": "medium"},
    {"cause": "metering_anomaly", "deterministic_score": "low"}
  ]
}
```

## What the AI is allowed to do

- Explain *why* the evidence is suspicious in plain language.
- Rank/discuss which candidate cause is most consistent with the evidence — using the deterministic scores as given, not recomputing them.
- Cite supporting evidence items from the evidence packet it was given (no free invention of new evidence).
- Suggest alternative explanations already present in `candidate_causes`, or a genuinely new plausible cause **only** if explicitly labeled as a suggestion outside the scored list (see schema below), never presented with a confidence number.
- Propose what an operator should check first, and what additional observation would help distinguish between competing causes.
- Phrase the recommended action in plain language, from the deterministic cause → action mapping.

## What the AI is NOT allowed to do

- Invent or change deviation percentages, severities, confidence scores, wastage volumes, cost, or CO2e figures.
- Introduce a candidate cause with a numeric confidence score not computed by the deterministic Investigation Engine.
- Decide whether an intervention is "verified" — that is a deterministic post-intervention comparison, full stop.
- Access raw historical telemetry directly or query the database — it only receives the evidence packet passed to it.

## Structured output contract

```json
{
  "likely_cause": "plumbing_leak",
  "reasoning": "Consumption remained elevated for 3 hours while the building was marked closed and occupancy was zero, which is inconsistent with occupancy-driven use and consistent with continuous, unattended flow.",
  "supporting_evidence": ["deviation_pct", "operating_status", "occupancy", "duration_hours"],
  "alternative_causes": ["irrigation_left_active", "metering_anomaly"],
  "distinguishing_check": "Check whether the irrigation controller has an active schedule during this window; if not, the leak explanation strengthens.",
  "recommended_action": "Inspect the second-floor washroom flush valve and supply line for a continuous leak."
}
```

`likely_cause` and `alternative_causes` must be members of the `candidate_causes` list already supplied (or the pipeline rejects the response and falls back — see below). `reasoning` and `distinguishing_check` are free text but are length- and content-checked (no numeric claims that don't match the input evidence).

## Validation before display

Every AI response is validated against a Pydantic schema before it reaches the frontend:

1. **Schema validation** — required fields present, correct types.
2. **Grounding validation** — `likely_cause` and every entry in `alternative_causes` must exist in the `candidate_causes` list that was sent; `supporting_evidence` entries must be evidence-packet field names that were actually sent.
3. **No-new-numbers check** — reject (regex/heuristic scan) if the reasoning text contains a percentage or currency figure that doesn't match a value present in the evidence packet, to catch the AI inventing a number in prose.
4. If any check fails → discarded, deterministic fallback engine runs instead, and the response is tagged `explanation_source: "fallback"`.

## Fallback behavior (must always work)

If the Anthropic API call errors, times out, is disabled, or fails validation:

- A deterministic fallback investigation engine builds the same structural output directly from the evidence packet and the rule-based `candidate_causes` scoring, using template text, e.g.:
  > "Consumption is {deviation_pct}% above baseline. The pattern most closely matches **{top_cause}** based on: {evidence_list}."
- `distinguishing_check` falls back to a static per-cause template (e.g., for `plumbing_leak`: "Check whether any tap, valve, or irrigation line was left open during this window.").
- `explanation_source` is set to `"fallback"` and surfaced (subtly) in the UI so it's transparent, not hidden, when the AI layer isn't in the loop.
- No user-facing error, no crash — the full detect → investigate → recommend → verify workflow is demonstrable end-to-end with the AI API key removed.

## Explicitly not built

- No open-ended chatbot / conversational interface.
- No AI-driven anomaly scoring or severity classification.
- No AI-driven savings/impact calculation.
- No AI write access to the database — it is a pure function: evidence packet in, structured explanation out.

## Implementation notes (Milestone 4)

The design above is implemented essentially as originally specified, with the output schema refined slightly during implementation — documented here as the actual, current contract.

### Final structured output schema

```json
{
  "likely_cause": "plumbing_leak",
  "observed": [
    "Consumption was 238% above the expected baseline for this time slot.",
    "Recorded occupancy was zero for most of this window."
  ],
  "inference": "Sustained elevated flow while the building was closed and unoccupied is inconsistent with normal use and consistent with a continuous, unattended leak.",
  "supporting_evidence": ["baseline_deviation", "operating_status", "occupancy"],
  "alternative_explanations": [
    {"cause": "irrigation_left_active", "why_less_likely": "Less consistent with the sustained, flat pattern than a leak."}
  ],
  "recommended_next_step": "Inspect fixtures and the incoming water line for continuous flow.",
  "reasoning_confidence": "high"
}
```

Two changes from the original draft schema, made deliberately during implementation:

- **`observed` / `inference` replace a single `reasoning` field** — implementing the "distinguish observation from inference" requirement directly in the schema rather than only in prose: `observed` may only restate facts literally present in the evidence packet (enforced by grounding validation, below), `inference` is where the model is allowed to reason.
- **`alternative_explanations` is now `[{cause, why_less_likely}]`** rather than a bare list of cause names — this makes the comparison against the likely cause explicit and forces the model to justify why each alternative is weaker, rather than just listing them.
- **`reasoning_confidence` is a strict `"high" | "medium" | "low"` enum**, never a numeric percentage — this is the AI's own qualitative confidence in its reasoning, kept explicitly separate from the deterministic `deterministic_score` (`high`/`medium`/`low`) already attached to each candidate cause by the Milestone 3 analytics engine. Neither confidence value is ever a number the AI invents.

### Grounding validation, concretely

`app/ai/grounding.py` implements the "no-new-numbers check" and cause/evidence grounding described above with three concrete checks, run after Pydantic schema validation:

1. `likely_cause` and every `alternative_explanations[].cause` must be a member of the `candidate_causes` list that was actually sent.
2. Every `supporting_evidence` entry must be a `signal` name that was actually present in the evidence packet's `evidence` list.
3. Every number found anywhere in the free-text fields (`inference`, `observed`, `recommended_next_step`, `why_less_likely`) must match — within a small tolerance, to allow for reasonable rounding in prose — a number that actually appears somewhere in the evidence packet. A number that doesn't match anything in the evidence packet fails validation.

Any failure at any of these three checks, or a Pydantic schema failure, or a JSON parse failure, discards the AI response entirely and falls back to `app/ai/fallback.py` — there is no partial-trust path.

### Fallback engine, concretely

`app/ai/fallback.py` builds the exact same `InvestigationResult` shape directly from the deterministic evidence packet: `likely_cause` = the top-ranked `candidate_causes` entry, `alternative_explanations` = the rest of that ranked list, `observed` = the evidence list's descriptions verbatim, `reasoning_confidence` = the top cause's own deterministic score. The fallback engine is held to the identical grounding validation as the AI path (tested directly — see `TESTING.md`) — it isn't given a free pass.

### Where the AI is actually invoked

`app/ai/investigation_service.investigate_anomaly()` is the single orchestration point, called from `POST /api/anomalies/{id}/investigate`. It takes an injectable `ai_provider` callable (`(system_prompt, user_prompt) -> str`), defaulting to `app/ai/client.call_anthropic` (the real Anthropic SDK call) — this is what lets the entire test suite run without a real API key or network access. Results are cached on the `Investigation` row and not recomputed unless `force=True` is passed.
