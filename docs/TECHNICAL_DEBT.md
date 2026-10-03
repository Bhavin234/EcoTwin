# Technical Debt

Compiled during the Milestone 8 hardening audit. Only genuine debt is listed — items that were merely *documented* limitations with no actual product risk are covered in `LIMITATIONS.md` instead and not duplicated here unless they also carry engineering debt.

## Must fix before any real (non-demo) deployment

| Item | Why it matters | Where |
|---|---|---|
| **SQLite as the default local database** | Fine for this sandbox and local development, but the product is designed and documented for PostgreSQL (`TECH_STACK.md`, `DEPLOYMENT.md`). SQLite has never been exercised under concurrent write load, and its lack of true `DateTime(timezone=True)` support (values round-trip as naive) is a real, if currently harmless, quirk. | `backend/app/core/database.py` |
| **No database migrations** | Tables are created via `Base.metadata.create_all()`, not Alembic. This is fine for an MVP with no production data to preserve, but any real schema change against a live database with existing rows needs a real migration tool. Flagged since `ARCHITECTURE.md`/Milestone 1. | `backend/app/core/database.py` |
| **No authentication** | Every endpoint is open. Explicitly out of MVP scope per the original brief, but this must be addressed before any deployment beyond a judged demo or trusted local use. | Entire API |

## Safe for the hackathon MVP (known, bounded, not worth fixing now)

| Item | Why it's acceptable for now |
|---|---|
| **`potential` impact kind is never populated** | Would currently just duplicate the `estimated` figure without a genuine forward-projection model (docs/LIMITATIONS.md). Not a bug — a deliberate scope decision. |
| **Verification's "contextual comparability" check is a match/mismatch guard, not a full occupancy-regression model** | Correctly downgrades confidence (`improvement_detected` vs. `verified`) on a context mismatch, but doesn't quantify how much of a change a partial context difference might explain. Documented in `LIMITATIONS.md`. |
| **Numeric grounding in `app/ai/grounding.py` is a tolerance-based heuristic** | Reliably catches invented/altered numbers (confirmed via 9 adversarial tests in `tests/hardening/test_ai_grounding_adversarial.py`), but is not a formal proof against every conceivable subtle misstatement in free-text reasoning. |
| **Emission/cost factor defaults are illustrative, not finalized citations** | `EMISSION_CALCULATIONS.md` states this explicitly; the registry and versioning/snapshotting mechanism (the actual engineering) is real and correct — only the seed *values* need a final citation before non-demo use. |
| **No rate limiting on the Anthropic API call** | A single-investigation-at-a-time demo workflow has no realistic way to run up a large bill; would need addressing for any multi-user deployment. |
| **CORS is configured for `localhost:5173` only by default** | Correct and secure for local development; would need updating (not loosening) for a real deployed frontend origin. |
| **No structured application logging/observability** | `print()`/`logger.info` statements exist but there's no log aggregation, request tracing, or metrics. Acceptable for a local judged demo. |

## Future product work (not debt — deliberately out of scope)

See `FUTURE_SCOPE.md` for the full list (real IoT/BMS integration, ML anomaly detection upgrade, multi-tenancy, fuel/waste resource types, automated actions, regulatory-grade emissions reporting, mobile notifications, sensor-drift detection). None of these are debt in the sense of "should have been built" — they were explicitly deferred from the MVP's start.

## Fixed during Milestone 8 (no longer debt)

- `analyze_resource`/`compute_causal_baselines` crashing on a genuinely empty DataFrame when called directly, rather than only being protected by the caller's own guard.
- No defense-in-depth rejection of negative consumption at the shared `bulk_insert_measurements` insertion point (only the CSV path validated it before).
- A pandas `FutureWarning` on a mixed-type occupancy column during `fillna`.
- **A reproducibility bug**: the Milestone 3 cross-process determinism regression test hardcoded an absolute sandbox path (`cwd="/home/claude/eco/backend"`), which would have broken for anyone running the test suite from a different clone location. Fixed to compute the backend root dynamically from `__file__`. Found during the reproducibility audit (docs Milestone 8, requirement #20), not by inspection alone.

See `TESTING.md`, "Milestones 6-8 status" for the adversarial tests that found each of these.
