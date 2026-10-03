# Testing Strategy (Revised)

## Scenario validation framework (new)

Six deterministic, reproducible scenarios (same ones used for the demo, see `DEMO.md`) are stored as fixtures in `backend/tests/scenarios/` and exercised by both unit and end-to-end tests:

1. Normal operation
2. Water leakage (sustained elevated flow, building closed, zero occupancy)
3. Electricity overconsumption (sustained elevated draw outside expected pattern)
4. Building closed but consumption continues (generalized version of leak-style anomaly, resource-agnostic)
5. Legitimate temporary spike (should NOT be classified `operationally_suspicious`)
6. Post-intervention recovery (consumption returns to baseline after a marked intervention)

Each scenario asserts the **expected severity classification and expected top candidate cause**, so a regression in the anomaly or investigation engine is caught immediately, and so we can demonstrate the system was validated against multiple plausible real-world patterns rather than one hand-picked example (directly addresses the "lack of real-world validation" limitation — see `LIMITATION_RESOLUTION_MATRIX.md`).

## Backend (pytest)

- **API endpoint tests** — happy path + error cases for every route in `API.md` (invalid CSV, missing columns, empty dataset, unknown resource type).
- **Data validation tests** — malformed/missing rows flagged without crashing.
- **Baseline tests** — known synthetic input → expected mean/stddev; cold-start (`insufficient_history`) path.
- **Multi-signal anomaly tests** — each scenario fixture → expected severity + classification (`unusual` vs `operationally_suspicious`).
- **Cause hypothesis tests** — fixed signal combinations → expected deterministic candidate-cause ratings.
- **AI Reasoning Layer tests** — (a) mock a valid AI response → confirm it passes validation and is stored with `explanation_source: "ai"`; (b) mock an invalid/ungrounded AI response (e.g., a `likely_cause` not in `candidate_causes`) → confirm it's rejected and fallback runs; (c) mock an AI timeout/error → confirm fallback runs with no unhandled exception.
- **Emission/cost tests** — known consumption + factor version → expected CO2e/cost, and confirm past `impact_records` are unaffected by a later factor update (snapshot behavior).
- **Verification tests** — pre/post synthetic windows → correct verified/no-change classification; confirm `verified` is never returned before the minimum post-intervention data gate is met.

## Frontend

Component tests for the highest-value interactive elements (Run Demo button, Mark Intervention Complete, CSV upload) if time allows; lower priority than backend correctness given judging weight on Usability/Innovation/Documentation over frontend unit coverage.

## End-to-end demo test

A scripted test against a test database running the full loop for the chosen demo scenario: load scenario → detect → investigate (AI + fallback both tested) → recommend → mark intervention complete → simulate improved post-intervention data → verify → assert impact numbers are produced and internally consistent (verified savings ≤ estimated wastage window; cost = consumption × configured rate; CO2e = consumption × factor). Run this before every judging session.

## Milestone 2 status (actual results)

40 automated tests, all passing, covering:

- **Simulator** (`tests/ingestion/test_telemetry_simulator.py`, 7 tests): determinism (same config+seed → identical output), a different seed changes noise, schema/record-count correctness, no negative consumption, weekday-operating-hours consumption clearly exceeds weekend, operating-hours consumption clearly exceeds closed-hours on the same weekday, occupancy is zero outside operating hours.
- **Scenarios** (`tests/ingestion/test_scenarios.py`, 7 tests): each of the 6 named scenarios produces its intended realistic pattern (verified statistically, not just "rows exist") — e.g. the water leak is sustained/flat and elevated relative to the known closed-hours baseline (not a single spike), the legitimate spike is occupancy-consistent and temporary, post-intervention recovery genuinely returns to baseline.
- **CSV ingestion** (`tests/ingestion/test_csv_source.py`, 11 tests): valid files accepted, optional columns may be omitted, empty/header-only files rejected, missing columns rejected, invalid timestamps/resource types/units/negative or non-numeric consumption all rejected with clear per-row messages, in-file duplicates rejected, multiple errors in one file all reported together (not just the first).
- **Service layer** (`tests/ingestion/test_telemetry_service.py`, 4 tests): location/resource get-or-create idempotency, duplicate-measurement skipping, filtered/paginated querying.
- **API** (`tests/ingestion/test_telemetry_api.py`, 7 tests): `/data/simulate` inserts and is idempotent on re-run, unknown scenario names are rejected with the documented error shape, `/measurements` pagination, `/data/upload` accepts valid CSVs and rejects invalid ones with the documented error shape, an unmatched filter returns an empty page rather than a 404.
- **Milestone 1 regression** (`tests/test_health.py`, 3 tests): still passing unchanged.

Run with: `pytest -v` from `backend/`.

A real bug was caught and fixed during this milestone by inspecting the generated data rather than only checking that tests passed: SQLAlchemy's default `Enum` column type persists the Python enum member *name* (e.g. `"ELECTRICITY"`) rather than its documented lowercase `.value` (`"electricity"`). Fixed with a shared `str_enum()` helper (see `DATA_MODEL.md`, "Implementation note"); full suite re-verified after the fix.

## Milestone 3 status (actual results)

93 automated tests total, all passing (56 new + 37 carried over from Milestone 2), covering:

- **Baseline engine** (`tests/analytics/test_baseline_engine.py`, 5 tests): cold-start `no_history` state, `sufficient` state after enough comparable slots, the `limited` resource-wide fallback, one snapshot per (hour, weekday) slot, and — the key correctness property — that a row's baseline never includes its own or a later value (verified with a deliberately-planted late outlier).
- **Deviation engine** (`test_deviation.py`, 6 tests): positive/negative deviation, zero-stddev handled via a floor instead of raising, near-zero-baseline-mean suppresses percentage but keeps z-score, tiny-baseline-with-tiny-actual doesn't explode, no-deviation gives exactly zero.
- **Persistence** (`test_persistence.py`, 6 tests): single reading, sustained run, a small gap still merges into one window, a large gap stays as two windows, no flags produces no windows, point-tier mapping.
- **Severity/classification** (`test_severity.py`, 7 tests): all four severity levels reachable with a documented reason, and the key false-positive-avoidance property — a large-but-brief-and-occupied deviation can reach an elevated severity score but is never classified `operationally_suspicious`.
- **Evidence** (`test_evidence.py`, 4 tests): percentage vs. z-score selection, context items only appear when the underlying signal actually fired, classification is reflected accurately.
- **Candidate causes** (`test_candidate_causes.py`, 4 tests): resource- and context-specific ranking for both electricity and water.
- **Cost/CO2e/savings** (`test_calculations.py`, 5 tests): factor-driven cost/CO2e math, and the excess/avoided split for the future savings workflow.
- **End-to-end scenario tests** (`test_anomaly_engine_scenarios.py`, 7 tests): the engine run against the real Milestone 2 scenario generators — normal operation raises nothing, the water leak and electricity overconsumption scenarios are independently discovered and classified `operationally_suspicious`, the closed-building scenario is strongly flagged on both resources, **the legitimate spike is never classified `operationally_suspicious`**, the full Greenfield demo story (leak → recovery) is correctly discovered end-to-end, and re-running an identical scenario produces byte-identical anomaly classifications.
- **Analytics API** (`test_analytics_api.py`, 8 tests): `/analysis/run` persists and summarizes correctly (and 404s cleanly for an unknown location), `/anomalies` list/detail/filtering, an `operationally_suspicious` anomaly has an Investigation with candidate causes and a null AI explanation (Milestone 4's job), `/config/factors` seeds and returns defaults, and both factor-update endpoints work.

Run with: `pytest -v` from `backend/`.

### Real bugs found and fixed during this milestone (by inspecting output, not just passing tests)

1. **Numpy types leaking into a JSON column.** `bool_series.mean() >= 0.5` returns `numpy.bool_`, not a Python `bool`; SQLite's JSON serializer rejected it when persisting `Anomaly.signals`. Fixed by explicitly casting to native Python types before persistence.
2. **A real false-positive flood during cold start.** Initially, a `limited`-state (resource-wide fallback) baseline was allowed to flag anomalies at a slightly higher threshold. For a resource with a strong diurnal swing (electricity), a resource-wide blended baseline is a poor predictor for any single hour, and this flooded the first ~2 weeks of the demo dataset with spurious flags. Fixed by only ever flagging from a `sufficient` (slot-specific) baseline — see `ANOMALY_DETECTION.md`, "Implementation notes."
3. **A cross-process determinism bug in the Milestone 2 simulator**, only surfaced by Milestone 3's more thorough analysis: the per-resource noise seed offset used Python's built-in `hash(str)`, which is randomized per-process (`PYTHONHASHSEED`) unless disabled. The *same* configured seed therefore produced *different* telemetry across separate runs of the program — invisible to a same-process determinism test, but a real break of the "same seed reproduces the same dataset" guarantee `DEMO.md` depends on. Fixed with `zlib.crc32` (not affected by hash randomization) and covered by a new regression test that runs the simulator in two separate subprocesses and compares output.

## Milestone 4 status (actual results)

130 automated tests total, all passing (37 new + 93 carried over from Milestones 1-3), covering:

- **Grounding validation** (`tests/ai/test_grounding.py`, 8 tests): a fully valid response passes; an invented `likely_cause`, an invented alternative cause, an invented `supporting_evidence` signal name, and an invented number in free text are each independently caught; referencing an evidence number verbatim (or lightly rounded, within tolerance) correctly passes; small numbers like persistence hours and occupancy are correctly allowed.
- **Deterministic fallback engine** (`tests/ai/test_fallback.py`, 6 tests): uses the top-ranked candidate cause, lists the remainder as alternatives, `observed` matches the evidence descriptions exactly, **passes its own grounding check** (held to the identical standard as the AI path, not a looser one), recommends a cause-specific next step, and doesn't crash on an empty candidate-cause list.
- **Investigation service** (`tests/ai/test_investigation_service.py`, 13 tests, all using a mocked AI provider — no real network/API key required): valid AI response accepted and persisted; malformed JSON, a schema-violating response, an ungrounded invented cause, a timeout, and a generic API failure all correctly trigger fallback; markdown-fenced JSON is still parsed; a missing API key falls back cleanly via the real default code path; a second call returns the cached result without re-invoking the provider, `force=True` re-invokes it; investigating a merely-`unusual` (not `operationally_suspicious`) anomaly raises; an unknown anomaly ID raises; the evidence packet actually reaching the provider is verified by capturing the real prompt text.
- **Evidence packet builder** (`tests/ai/test_evidence_packet.py`, 2 tests): every documented section is present, and its numbers match the persisted `Anomaly` row exactly.
- **Investigation API** (`tests/ai/test_investigation_api.py`, 8 tests): the real end-to-end fallback path with no API key configured, AI-path success via a monkeypatched provider, fallback-on-invalid-JSON via the API, persistence reflected in `GET /anomalies/{id}`, caching behavior via the API (`force` query param), 422 for a merely-`unusual` anomaly, 404 for an unknown anomaly, and confirmation the API key never appears in any response.

Run with: `pytest -v` from `backend/`.

### A real bug found via test isolation, not application logic

While writing these tests, several appeared to fail with the *previous* test's AI-generated result instead of their own — not an application bug, but a test-helper bug: `_seed_suspicious_anomaly()` queried `Anomaly` for `classification == operationally_suspicious` **without filtering by location**, so on the shared session-scoped test database it silently returned an already-investigated anomaly from an earlier test in the file instead of the fresh one just created. Fixed by joining through `Resource` and filtering by `location_id`. Documented here because it's a useful cautionary example for future milestones: test helpers that query by a coarse global condition on a shared test database can silently return the wrong record if they don't also scope by the entity the test actually created.

### Real (manual) Greenfield investigation, no API key configured

```bash
cd backend && python -m app.cli seed-demo --reset && python -m app.cli investigate-demo
```

produces the full transcript in `DEMO.md`, "Implementation notes (Milestone 4)" — `plumbing_leak` at `high` confidence, evidence-grounded, with alternative explanations and a concrete recommended inspection step, clearly labeled `FALLBACK` since no `ANTHROPIC_API_KEY` is set in this sandbox.

## Milestone 5 status (actual results)

165 automated tests total, all passing (35 new + 130 carried over from Milestones 1-4), covering:

- **Recommendation service** (`tests/services/test_recommendation_service.py`, 5 tests): created after investigation for both water and electricity anomalies, priority correctly derived from severity, an estimated `ImpactRecord` is created with a full factor snapshot, and re-investigating (force) doesn't duplicate either the Recommendation or its estimated impact record.
- **Intervention service** (`tests/services/test_intervention_service.py`, 8 tests): creation, idempotent re-creation, failure when no Recommendation exists yet, completion sets status/timestamp without touching `verification_status`, completion defaults to "now" when no timestamp given, completing twice is an idempotent no-op (not an error), and unknown-ID errors for both creation and completion.
- **Verification service** (`tests/services/test_verification_service.py`, 8 tests): genuine improvement is `verified` with a persisted `verified` impact record; a dishonestly-early completion (still inside the leak window) correctly produces `no_measurable_improvement` with **no** impact record created; completing far beyond available telemetry produces `insufficient_data`; verifying an incomplete intervention raises; unknown intervention ID raises; and a white-box test confirms the contextual-comparability guard downgrades an otherwise-normal-looking result to `improvement_detected` rather than `verified` when the recorded context doesn't match.
- **Demo workflow** (`tests/services/test_demo_service.py`, 3 tests): the full Greenfield story completes end-to-end and reaches `verified`; calling it twice reuses the same anomaly/investigation/recommendation/intervention rather than duplicating; three calls in a row don't accumulate duplicate impact records.
- **Intervention/impact/demo API** (`tests/services/test_intervention_api.py`, 9 tests): the full lifecycle via HTTP, the investigation response includes its recommendation, duplicate-creation returns the same intervention, verifying before completing returns 422, `/impact` aggregates across kinds and filters by location, `/demo/run` completes and is idempotent via the API too, and 404 for an unknown intervention.
- **Numerical integrity, adversarially** (`tests/services/test_numerical_integrity.py`, 3 tests): an AI response that actively asserts specific savings/CO2e/"fully verified" figures is correctly rejected by grounding validation (falls back); even independent of that, the persisted `Recommendation.estimated_saving` never matches the adversarial numbers and `Intervention.verification_status` is never set to anything but what the deterministic engine computes; and the complete loop still produces correct real numbers with AI entirely unavailable.

Run with: `pytest -v` from `backend/`.

### Test bugs found and fixed this milestone (not application bugs)

Two test assertions initially failed by comparing a tz-aware Python literal directly against a value that had round-tripped through SQLite (which, as documented since Milestone 2, doesn't persist `tzinfo` even for a `DateTime(timezone=True)` column). Fixed by normalizing before comparison in the tests themselves — the application's internal logic was never affected, since it consistently reads timestamps back from the same database rather than mixing a fresh literal with a round-tripped value.

### Real (manual) Greenfield end-to-end run

```bash
cd backend && python -m app.cli seed-demo --reset && python -m app.cli run-demo
```

produces the full transcript in `DEMO.md`, "Implementation notes (Milestone 5)" — `VERIFIED`, ~39 units avoided, real cost/CO2e figures, all derived from actual telemetry, not asserted.

## Milestones 6-8 status (actual results)

**239 automated tests total, all passing: 203 backend (pytest) + 36 frontend (vitest/Testing Library).**

- **Milestone 6 (frontend)** — 20 tests: StatusBadge, EvidenceList, AIInvestigationPanel (honest AI/fallback labeling), RecommendationPanel, a mocked-backend InvestigationDetail integration test, and an App-level navigation smoke test.
- **Milestone 7 (demo experience)** — 11 more frontend tests (31 total) covering the investigation timeline, the deterministic/AI methodology split, and the demo runner's honest progress + reset-and-rerun flow; 7 more backend tests (174 total) covering demo reset scoping and the enriched demo result fields.
- **Milestone 8 (hardening)** — 29 more backend tests (203 total, `tests/hardening/`) covering adversarial data (empty dataset, single measurement, missing occupancy/operating status, zero/tiny/huge consumption, duplicate/out-of-order timestamps, negative consumption rejection), adversarial AI grounding (invented percentages, causes, evidence signals, savings claims, and false "verified" claims — all independently confirmed rejected), intervention/verification edge cases (immediate completion, halfway completion, missing post-data, repeated verification/completion), and database integrity (repeated demo runs + reset leave no orphaned rows, reset never touches other locations); 5 more frontend tests (36 total, `FailureHandling.test.jsx`, `RefreshRecovery.test.jsx`) covering backend-offline, 500, malformed-error-body, and fresh-mount state recovery.

### Real bugs found and fixed during Milestone 8 (by adversarial testing, not by inspection alone)

1. **`analyze_resource`/`compute_causal_baselines` crashed on a genuinely empty DataFrame** when called directly (the higher-level `analytics_service.run_analysis_for_location` happened to guard against this with its own `if df.empty` check, but the lower-level function wasn't robust on its own — a latent bug any future caller could have hit). Fixed by making `compute_causal_baselines` return an empty, correctly-typed DataFrame for empty input instead of raising.
2. **Negative consumption had no defense-in-depth check** at the shared `bulk_insert_measurements` insertion point — only the CSV upload path validated it, so a hypothetical future ingestion source (e.g., a direct API push) could have silently accepted physically impossible telemetry. Fixed by rejecting negative consumption at the one insertion point every source goes through.
3. **A pandas `FutureWarning`** on `fillna` with a mixed-type occupancy column, surfaced by the missing-occupancy adversarial test. Fixed by coercing to numeric before filling.
4. **A reproducibility bug in a Milestone 3 test**: the cross-process determinism regression test hardcoded an absolute sandbox path (`cwd="/home/claude/eco/backend"`) rather than computing it dynamically — found during this milestone's explicit reproducibility audit (requirement #20), not by inspection. Fixed to derive the path from `__file__`.

See `HACKATHON_READINESS.md` and `TECHNICAL_DEBT.md` for the full audit results.
