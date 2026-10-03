# Reliability & Trust

EcoTwin is not an LLM wrapper. This document lays out, in one place, why the system stays trustworthy even when the AI layer is unavailable, wrong, or unreachable.

## Deterministic calculations

Every number that drives a decision — baseline mean/stddev, deviation percentage, z-score, severity, wastage volume, cost, CO2e, savings, and confidence ratings on candidate causes — is computed by backend statistical/arithmetic code (`ANOMALY_DETECTION.md`, `EMISSION_CALCULATIONS.md`, `DATA_MODEL.md`). The AI never computes, invents, or silently adjusts any of these values.

## AI boundaries

The AI Reasoning Layer receives a structured evidence packet and deterministic candidate-cause ratings, and returns a structured explanation. It cannot introduce a new numeric confidence, alter a severity, or change an impact figure. Full contract in `AI_ARCHITECTURE.md`.

## Structured AI outputs + validation

AI responses are required to match a defined schema (`likely_cause`, `reasoning`, `supporting_evidence`, `alternative_causes`, `distinguishing_check`, `recommended_action`) and are validated for:
1. Schema correctness
2. Grounding — cited causes/evidence must exist in what was actually sent
3. No invented numbers in free text

Any response failing validation is discarded, not partially trusted or silently patched.

## Fallback behavior

If the AI API errors, times out, is disabled, or fails validation, a deterministic rule-based fallback engine produces an equivalent structured explanation from the same evidence and candidate-cause scores. The full detect → investigate → recommend → intervene → verify loop works with zero AI involvement. `explanation_source` (`ai` \| `fallback`) is always recorded and can be surfaced in the UI.

## Data validation

Incoming measurements (CSV, simulator, or future API push) are validated and normalized by the Data Agent before anything downstream sees them — missing values, malformed rows, and unknown resource types are flagged and handled, never silently dropped or silently guessed.

## Anomaly scoring

Multi-signal, persistence-aware scoring (not a single-metric threshold) with four severity levels and an explicit `unusual` vs `operationally_suspicious` distinction — designed specifically to reduce false positives and alert fatigue (`ANOMALY_DETECTION.md`).

## Emission-factor management

Emission and cost factors live in a versioned, cited, configurable registry — never hardcoded inline — and past impact figures are snapshotted against the factor version used, so they don't silently change if the registry is updated later (`EMISSION_CALCULATIONS.md`, `DATA_MODEL.md`).

## Intervention verification

An intervention is only ever labeled "verified" once a minimum amount of post-intervention data has been collected and directly compared against the same baseline slot used to detect the original anomaly. Before that gate is met, the system reports "pending verification," never a premature success claim.

## Estimated vs. verified impact

Every impact figure is labeled `potential`, `estimated`, or `verified` and these are never merged into one undifferentiated "savings" number — a deliberate design choice to avoid overclaiming, reflected end-to-end from the database schema through the API to the UI.

## Reproducibility of demo scenarios

Demo/scenario telemetry is generated deterministically and checked into the repository (`data/demo_scenarios/`), not randomly regenerated at runtime — the same demo run produces the same anomaly, evidence, and outcome every time, which is what makes the scenario validation framework in `TESTING.md` meaningful and what makes the judging demo reproducible.

## Net effect

A judge (or future developer) can audit every number EcoTwin shows back to a deterministic calculation, can see the AI is constrained to reasoning over evidence it didn't generate, and can watch the system continue to function correctly with the AI switched off. That combination — not any single technique — is what makes EcoTwin trustworthy rather than a demo that only works when a language model happens to answer well.

## Implementation status (Milestone 3)

The deterministic side of this document is now real, not aspirational: baselines, deviation, persistence, severity, classification, evidence, candidate causes, and cost/CO2e calculations are all implemented in `app/analytics/` and verified against the actual Greenfield Public School demo dataset (10 weeks, hourly resolution) — not just unit tests in isolation. The engine independently discovered the injected water leak as a single HIGH-severity, `operationally_suspicious` anomaly with `plumbing_leak` ranked as the top cause, and raised zero false `operationally_suspicious` classifications anywhere else across both resources' full history. Two real bugs (a JSON-serialization issue and a cold-start false-positive flood) were caught this way and fixed — see `TESTING.md` for detail. The AI Reasoning Layer itself, and its validation/fallback behavior, remain Milestone 4.

## Implementation status (Milestone 4)

The AI Reasoning Layer is implemented and its boundaries are enforced in code, not just prompt instructions:

- **Structured input only.** The AI never sees raw telemetry or the database — only the evidence packet `app/ai/evidence_packet.py` builds from already-computed deterministic data (Milestone 3's `Anomaly.signals` and `Investigation.candidate_causes`).
- **Structured output, validated in two layers.** Pydantic schema validation (shape) followed by grounding validation (`app/ai/grounding.py`: content — every cause, evidence reference, and number must trace back to the evidence packet). Either failure discards the response.
- **Deterministic fallback, held to the same standard.** `app/ai/fallback.py` produces the same schema from the same evidence, and is tested against the identical grounding validator the AI path uses — there's no separate, looser bar for the fallback path.
- **Never fakes AI.** `explanation_source` (`"ai"` \| `"fallback"`) is always recorded accurately; the fallback reason is preserved and surfaced, and the deterministic path never claims to be AI output.
- **Verified against the real Greenfield Public School dataset.** With no `ANTHROPIC_API_KEY` configured in this environment (the normal state for this sandbox), `python -m app.cli investigate-demo` runs the actual water-leak anomaly discovered in Milestone 3 through the full investigation pipeline end-to-end, correctly falls back, and produces a complete, evidence-grounded investigation (`plumbing_leak`, high confidence, with alternative explanations and a recommended inspection) — see `DEMO.md` for the full transcript.
- **API key never leaves the server.** Read once from server-side config (`app.core.config`), passed only to the Anthropic SDK client, never included in any API response or log line — tested explicitly (`tests/ai/test_investigation_api.py::test_api_key_never_appears_in_any_response`).

## Implementation status (Milestone 5)

The closed loop is now real end to end, and every number in it remains deterministic:

- **Recommendations**: `action_text` may come from the AI/fallback investigation's `recommended_next_step`; `priority` and `estimated_saving` are always computed by `app/services/recommendation_service.py` from the anomaly's own signals — the AI never determines either.
- **Intervention lifecycle vs. verification are separate claims.** Completing an intervention (`status="completed"`) never advances `verification_status` — only an explicit, always-recomputed `POST /interventions/{id}/verify` call can. Verified with real data: dishonestly marking an intervention complete *during* an ongoing leak correctly produces `no_measurable_improvement`, not a false `verified`.
- **Verification reuses the Milestone 3 baseline/deviation engine exactly** — no second methodology — and adds an explicit "contextual comparability" guard (docs/ANOMALY_DETECTION.md) so a change in operating context between the anomaly and verification windows downgrades confidence rather than being silently ignored.
- **Numerical integrity tested adversarially.** `tests/services/test_numerical_integrity.py` feeds the investigation pipeline a deliberately fabricated AI response claiming specific savings/CO2e/verification figures; grounding validation rejects it (falls back), and even where it wouldn't, the persisted `Recommendation.estimated_saving` and `Intervention.verification_status` are shown to never reflect anything the AI text asserted — only `app/analytics/calculations.py` and `app/services/verification_service.py` ever set those fields.
- **Factor snapshotting implemented** (deferred from Milestone 3) — see `EMISSION_CALCULATIONS.md`.
- **Verified against the real Greenfield Public School dataset end to end**: `python -m app.cli run-demo` runs seed → analyze → investigate → recommend → intervene → complete → verify with no AI key configured, and produces `VERIFIED`, with avoided consumption, cost, and CO2e all computed from real telemetry — see `DEMO.md` for the transcript.
