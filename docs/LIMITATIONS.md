# Limitations (MVP)

This file is retained as the engineering checklist it started as. Each item below is now cross-referenced to `LIMITATION_RESOLUTION_MATRIX.md`, which shows the concrete solution chosen for the MVP rather than only naming the gap. Read the two files together — this one states the limitation plainly, the matrix shows what we actually did about it.

- **No real hardware integration.** Data comes from CSV upload or the deterministic telemetry simulator. → See matrix: hardware-agnostic ingestion interface, ready for future IoT/BMS without a rewrite (`FUTURE_SCOPE.md`).
- **CO2e figures are estimates**, not audited measurements. → See matrix: versioned, cited, configurable emission-factor registry (`EMISSION_CALCULATIONS.md`).
- **Cause hypotheses are drawn from a fixed, documented signal set.** → See matrix: multi-signal scoring, explicitly documented (`ANOMALY_DETECTION.md`); will not capture causes with no signature in the available signals.
- **AI reasoning can only be as good as its grounding validation.** → See matrix (AI hallucination row): every cause, evidence reference, and number in an AI response is checked against the evidence packet it was given; anything ungrounded is discarded in favor of the deterministic fallback. This catches invented/altered facts reliably but is a heuristic, not a formal guarantee against every possible subtle misstatement in free-text reasoning.
- **A `potential` impact figure (what an open, un-acted-on recommendation would save if the condition continued) is not yet separately modeled.** → It would currently just duplicate the `estimated` figure without a genuine forward-projection model; deferred as a deliberate scope decision rather than persisting a redundant number — see `FUTURE_SCOPE.md`.
- **Verification's "contextual comparability" check is a simple match/mismatch guard, not a full occupancy-regression model.** → It correctly downgrades confidence (`improvement_detected` instead of `verified`) when the post-intervention window's operating context doesn't match the original anomaly's, but doesn't quantify *how much* of a reduction a partial context change might explain — deferred as a future refinement (`FUTURE_SCOPE.md`).
- **Statistical, not ML-based, anomaly detection**, chosen for explainability and to work without pre-existing training data. → See matrix; ML upgrade path documented in `FUTURE_SCOPE.md`.
- **Single seeded demo account**, not multi-tenant enterprise auth/RBAC. → Out of MVP scope; `FUTURE_SCOPE.md`.
- **Verification requires a minimum amount of post-intervention data** before a claim is labeled "verified." → See matrix: explicit gate, demo compresses this using pre-generated deterministic post-intervention data, not a shortcut in the underlying logic.
- **Single-organization/single-site focus** for the MVP. → See matrix (scalability row): generic Resource/Measurement architecture is ready to extend, multi-tenancy itself is future scope.
- **Simulated demo data, however realistic, is not real-world sensor data.** → See matrix: proper deterministic simulator with seasonality/noise/occupancy modeling and multiple validated scenarios, explicitly disclosed rather than hidden.

See `LIMITATION_RESOLUTION_MATRIX.md` for the full Limitation → Risk → Solution → Implemented? → Result → Remaining Gap breakdown.
