# API Design (Revised)

Base path `/api`. FastAPI auto-generates OpenAPI docs at `/docs`; this file is the human-readable companion.

| Method | Path | Purpose |
|---|---|---|
| GET | `/locations` | List locations *(implemented Milestone 2)* |
| GET | `/resources` | List tracked resources (electricity/water per location) — filterable by `location_id`, `resource_type` |
| GET | `/measurements` | Query raw measurements (filters: `resource_id`, `location_id`, `resource_type`, `start`, `end`; paginated via `limit`/`offset`) |
| POST | `/data/upload` | Upload CSV (multipart `file` field); runs full validation before inserting anything (all-or-nothing) |
| POST | `/data/simulate` | Run the deterministic telemetry simulator for a chosen scenario (`normal_operation`, `water_leak`, `electricity_overconsumption`, `closed_building_consumption`, `legitimate_spike`, `post_intervention_recovery`) |
| GET | `/anomalies` | List anomalies (filters: `resource_id`, `location_id`, `resource_type`, `severity`, `status`, `classification`) *(implemented Milestone 3)* |
| GET | `/anomalies/{id}` | Anomaly detail, including full signal/evidence packet and its Investigation (candidate causes) if one exists *(implemented Milestone 3)* |
| POST | `/anomalies/{id}/investigate` | Run (or return the cached result of) an AI investigation for an `operationally_suspicious` anomaly *(implemented Milestone 4)*. Body: `{"force": bool}` (optional, default `false` — pass `true` to re-run instead of returning the cached result). Uses the real Anthropic API if `ANTHROPIC_API_KEY` is configured and its response passes schema + grounding validation; otherwise transparently uses the deterministic fallback engine. Returns `{anomaly_id, investigation_id, explanation_source, result, fallback_reason}` where `explanation_source` is always `"ai"` or `"fallback"` and `fallback_reason` is populated only when fallback was used. Returns 422 if the anomaly is classified `unusual` rather than `operationally_suspicious` (only suspicious anomalies get a full investigation), 404 if the anomaly doesn't exist. |
| POST | `/investigations/{id}/interventions` | Create an Intervention from an investigation's Recommendation *(implemented Milestone 5)*. Idempotent — returns the existing Intervention if one already exists. 422 if the investigation has no Recommendation yet (run `/investigate` first), 404 if the investigation doesn't exist. |
| GET | `/interventions/{id}` | Intervention detail: lifecycle `status`, `verification_status`, `marked_complete_at` *(implemented Milestone 5)* |
| POST | `/interventions/{id}/complete` | Mark intervention complete *(implemented Milestone 5)*. Body: `{"completed_at": datetime}` (optional, defaults to now). Sets `status="completed"`; `verification_status` stays `"pending"` — completion and verification are different claims. Idempotent (a second call is a no-op, not an error). |
| POST | `/interventions/{id}/verify` | Run (and persist) deterministic verification *(implemented Milestone 5)*. 422 if the intervention isn't completed yet. Safe to call repeatedly — always recomputes from current telemetry. Returns the verification state, the post-intervention vs. ordinary-baseline comparison, and the avoided-consumption/cost/CO2e figures compared against the counterfactual of the anomaly continuing (see `ANOMALY_DETECTION.md`, "Verification"). |
| GET | `/impact` | Aggregate potential / estimated / verified savings *(implemented Milestone 5)*. Filters: `location_id`, `resource_type`. Returns per-`kind` summaries plus the underlying records. |
| POST | `/demo/run` | Run (or resume) the complete backend demo workflow for one location: seed → analyze → investigate → recommend → intervene → complete → verify *(implemented Milestone 5)*. Idempotent — safe to call repeatedly; resumes from whatever state the location is already in rather than duplicating rows. This is the endpoint the frontend's "Run EcoTwin Demo" button calls directly (Milestone 6/7). |
| POST | `/analysis/run` | Run the deterministic baseline + anomaly engine for every resource at a location, persisting Baseline/Anomaly/Investigation rows *(implemented Milestone 3, not in the original plan — added because the engine needs an explicit trigger; equivalent in spirit to `/demo/run` but for analysis only, no AI)* |
| GET | `/config/factors` | List configurable cost/emission factors (seeds illustrative defaults on first call) *(implemented Milestone 3)* |
| PUT | `/config/factors/cost/{id}` | Update a cost factor's rate *(implemented Milestone 3; split from a single `/config/factors/{id}` into `cost` and `emission` sub-paths since they're different tables with different fields)* |
| PUT | `/config/factors/emission/{id}` | Update an emission factor's value/source/version *(implemented Milestone 3)* |

## Conventions

- List endpoints paginate via `?limit=&offset=`, return `{items, total, limit, offset}` (implemented for `/measurements`).
- Errors: `{error: {code, message, details?}}` — enforced globally by shared FastAPI exception handlers (`app/core/errors.py`), covering explicit `HTTPException`s, request validation errors, and any unhandled exception (which is logged server-side and never leaks a stack trace to the client).
- CSV upload validation errors return HTTP 422 with `error.code = "csv_validation_failed"` and `error.details` listing every row-level problem found, not just the first (nothing is partially inserted).
- `/data/simulate` is idempotent for a given `(location_name, scenario, seed, weeks)`: measurements are deduplicated by `(resource_id, timestamp)`, so re-running it reports `skipped_duplicates` instead of inserting twice.
- Anomaly/investigation responses include `explanation_source` (`ai` \| `fallback`) *(implemented Milestone 4)* — the frontend never has to guess which path produced a given explanation. Impact records include `kind` (`potential` \| `estimated` \| `verified`) *(implemented Milestone 5)* — `potential` is not yet populated by any code path (see `LIMITATIONS.md`), `estimated` and `verified` both are.
- `/anomalies/{id}` returns the full `signals` object exactly as used for severity classification (implemented Milestone 3) — evidence shown to the user is provably the same data that drove the classification, not a separately-written summary. Its nested `investigation` field is populated by Milestone 4 and is `null` for anomalies that haven't been investigated yet (or are merely `unusual`, which never get an Investigation row at all).

## Milestone 6 additions (frontend-driven, read-only)

| Method | Path | Purpose |
|---|---|---|
| GET | `/resources/{id}/baselines` | Persisted baseline snapshots for a resource (all hour/weekday slots) — added so the frontend can show "current vs. baseline" without recomputing anything client-side. |

`GET /anomalies/{id}` now also returns `evidence: list[dict]` (previously only reachable internally) and `investigation.recommendation.intervention` (so the frontend can tell in one call whether an intervention already exists for an investigation, without an extra round-trip or an implicit create-on-view).

## Milestone 7 additions

| Method | Path | Purpose |
|---|---|---|
| POST | `/demo/reset` | Fully clears one named demo location's data (scoped — never touches other locations), so the next `/demo/run` starts genuinely fresh. Body: `{"location_name": str}` (optional, defaults to "Greenfield Public School"). Returns `{reset: bool, location_name: str}` — `reset: false` if the location didn't exist (nothing to reset). |

`POST /demo/run`'s response now also includes `resource_type`, `deviation_pct`, `z_score`, `persistence_hours`, `majority_closed`, and `majority_zero_occupancy` — surfacing already-computed anomaly signal fields so the frontend's demo completion screen can show building status/occupancy/deviation/duration without an extra request.
