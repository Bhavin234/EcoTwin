# Data Model (Revised — Simplified, Generic Resource Architecture)

## Design principle

Electricity and water share the same underlying tables. There is no per-resource-type table duplication — a `resource_type` column and configurable `cost_factor`/`emission_factor` references are enough. This keeps the schema small (per the "no unnecessary enterprise complexity" instruction) and means adding a third resource type later (e.g., fuel) requires no schema change, only new config rows.

## Entity flow

```text
Location → Resource → Measurement → Anomaly → Investigation → Recommendation → Intervention → Impact
```

## Tables

### locations
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| name | text | e.g. "Floor 2" |
| timezone | text | for correct hour-of-day baselines |
| operating_hours | jsonb | e.g. `{"mon": ["09:00","18:00"], ...}` — drives `operating_status` |

*(No `organizations` table for the MVP — single-tenant demo scope; multi-tenancy is `FUTURE_SCOPE.md`.)*

### resources
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| location_id | uuid FK | |
| resource_type | enum | `electricity` \| `water` (MVP scope) |
| unit | text | kWh / L |
| cost_factor_id | uuid FK → cost_factors | |
| emission_factor_id | uuid FK → emission_factors | |

### measurements
| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| resource_id | uuid FK | indexed with timestamp |
| timestamp | timestamptz | |
| consumption | numeric | |
| occupancy | integer nullable | |
| source | enum | `csv` \| `simulator` \| `api` |
| scenario | text nullable | *(added during Milestone 2 implementation)* which named simulator scenario produced this row (e.g. `"water_leak"`), null for CSV/API rows. Purely descriptive metadata for development/test inspection — never an anomaly flag; the Anomaly Engine (Milestone 3) must still discover anomalies from the values and context alone. |

### baselines (derived/cached)
| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| resource_id | uuid FK | |
| hour_of_day | int | |
| day_of_week | int | |
| mean | numeric | |
| stddev | numeric | |
| sample_count | int | drives cold-start gating |
| computed_at | timestamptz | |

### anomalies
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| resource_id | uuid FK | |
| detected_at | timestamptz | |
| window_start / window_end | timestamptz | |
| severity | enum | `low` \| `medium` \| `high` \| `critical` |
| deviation_pct | numeric | |
| z_score | numeric | |
| signals | jsonb | the full signal packet (persistence, operating_status, occupancy, pattern_match, correlation) — same data shown as "evidence" |
| classification | enum | `unusual` \| `operationally_suspicious` |
| status | enum | `open` \| `investigating` \| `resolved` \| `dismissed` |

### investigations
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| anomaly_id | uuid FK, unique | |
| candidate_causes | jsonb | `[{cause, deterministic_score}]` |
| ai_response | jsonb nullable | validated structured AI output, or null if fallback used |
| explanation_source | enum | `ai` \| `fallback` |
| top_cause | text | denormalized |

### recommendations
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| investigation_id | uuid FK | |
| action_text | text | |
| priority | enum | `low` \| `medium` \| `high` |
| estimated_saving | numeric | |

### interventions
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| recommendation_id | uuid FK | |
| marked_complete_at | timestamptz | |
| status | enum | `recommended` \| `in_progress` \| `completed` — *(revised Milestone 5)* action lifecycle only: has the recommended action been carried out? |
| verification_status | enum | `pending` \| `insufficient_data` \| `no_measurable_improvement` \| `improvement_detected` \| `verified` — *(added Milestone 5)* a separate, deterministic outcome of comparing post-intervention telemetry against baseline. Deliberately distinct from `status`: completing an intervention never sets this to anything but `pending` — only `POST /api/interventions/{id}/verify` can advance it. |

**Why this changed from the original draft.** The Milestone 1 draft schema had `status` do double duty (`pending_verification` / `verified_success` / `verified_no_change`), written before the verification workflow existed to justify separating the two concepts. Milestone 5 splits them: `status` is now a simple 3-state lifecycle, and `verification_status` is the richer, honest set of outcomes the brief calls for (a large middle ground between "still broken" and "verified" — see `ANOMALY_DETECTION.md`/`RELIABILITY_AND_TRUST.md` for the methodology that produces each state).

### impact_records
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| intervention_id | uuid FK nullable | null for pre-intervention `estimated` records |
| anomaly_id | uuid FK nullable | *(added Milestone 5)* links a pre-intervention `estimated` record directly to the anomaly it came from — `intervention_id` alone can't express "before any intervention exists" |
| resource_id | uuid FK nullable | *(added Milestone 5)* deliberate denormalization for simple aggregation queries (`GET /api/impact`) without needing to know whether a record traces back via `anomaly` or via `intervention → recommendation → investigation → anomaly` |
| kind | enum | `potential` \| `estimated` \| `verified` — see semantics below |
| water_saved / energy_saved | numeric nullable | |
| co2e_avoided_kg | numeric | |
| money_saved | numeric | |
| window_start / window_end | timestamptz | |
| emission_factor_value_used, emission_factor_version, emission_factor_source | numeric/text nullable | *(added Milestone 5)* snapshot of the emission factor actually used, so a later edit to the live registry never retroactively changes a historical figure |
| cost_factor_rate_used, cost_factor_currency | numeric/text nullable | *(added Milestone 5)* same idea for cost |

**Factor snapshotting, implemented.** Milestone 3 deferred this ("snapshotting the factor value onto each impact_records row... is deferred to Milestone 5 when impact_records are actually written"). Now implemented as above.

**`potential` is not yet populated.** The MVP produces `estimated` (as soon as an anomaly is investigated) and `verified` (after successful verification). A `potential` record — "what an open, not-yet-acted-on recommendation would save if the underlying condition continued" — is conceptually distinct but would currently just equal the `estimated` figure without a genuine forward-projection model; rather than persist a duplicate, redundant number, this is deferred and documented in `LIMITATIONS.md`/`FUTURE_SCOPE.md` as a deliberate scope decision.

### cost_factors
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| resource_type | enum | |
| rate | numeric | ₹ per unit |
| effective_from | date | |

### emission_factors
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| resource_type | enum | |
| factor_value | numeric | kg CO2e per unit (water: embedded-energy proxy, see `EMISSION_CALCULATIONS.md`) |
| source | text | cited public source |
| version | text | |
| effective_from | date | |

Both factor tables are configuration data, editable without a code change — satisfies the "no hardcoded scattered factors" requirement.

## Impact terminology (unchanged, reinforced)

- **Potential** — projected savings if an open recommendation is acted on (not yet real).
- **Estimated** — impact calculated for a specific detected anomaly window, pre-verification.
- **Verified** — confirmed by the Verification Engine comparing real post-intervention data against baseline, only once the minimum post-intervention data gate is met.

## What was deliberately left out (per "avoid unnecessary complexity")

- No `organizations` / multi-tenancy table.
- No `waste` or `fuel` resource type rows for MVP (schema supports adding them later without migration beyond a new enum value).
- No permissions/roles tables — single seeded demo account.

## Implementation note (Milestone 2)

All enum-typed columns (`resource_type`, `operating_status`, `source`, `severity`, etc.) are stored as their lowercase string `.value` (e.g. `"electricity"`, `"closed"`) via a shared `str_enum()` helper, not SQLAlchemy's default of the Python member name — this keeps the database contents exactly matching the values documented above and returned by the API. Enums use `native_enum=False` (plain VARCHAR + CHECK constraint) so the same model code works unchanged on both SQLite (local dev/tests) and PostgreSQL (production).
