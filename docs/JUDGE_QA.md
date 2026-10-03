# Judge Q&A

Concise, honest answers prepared for likely questions. Where something isn't proven, that's said directly rather than implied otherwise.

## Product

**What problem does EcoTwin solve?**
Resource waste (a leak, equipment left running, a metering fault) often goes unnoticed for weeks because nobody is watching consumption continuously, and even when a dashboard flags "usage went up," nobody investigates why or checks whether a fix actually worked. EcoTwin closes that loop: detect → investigate → recommend → intervene → verify.

**Who would use it?**
Single-site or small-multi-site organizations without a dedicated facilities/energy management team — schools, small offices, retail, hotels, restaurants — the segment enterprise energy platforms and hardware-coupled IoT meters both under-serve (see `COMPETITIVE_ANALYSIS.md`).

**Why is this needed?**
Because in that segment, waste is usually caught by accident (someone notices a water bill spike weeks later), not by a system that watches, explains, and confirms.

**Why not simply use a standard energy dashboard?**
A standard dashboard answers "what happened." EcoTwin also answers "why," "what should we do," and — the part almost nothing in this space does well for this segment — "did it actually work," with a real before/after comparison against a statistical baseline, not just a before/after eyeball check.

## Technical

**How is the anomaly detected?**
A rolling, causal (never-uses-future-data) baseline per (resource, hour-of-day, day-of-week) slot, compared against actual consumption via a z-score with a floored standard deviation (to avoid instability from near-zero-variance baselines). Multiple signals — deviation magnitude, persistence (consecutive flagged readings), operating status, occupancy, cross-resource correlation — combine into a documented point-based severity score. See `ANOMALY_DETECTION.md`.

**How is the baseline calculated?**
For each hour-of-day/day-of-week slot, the mean and standard deviation of up to the last 8 comparable prior occurrences — causally, so a reading is never used to compute its own expected value. Below 3 prior samples for a slot, the system falls back to a resource-wide baseline for display but never uses it to flag an anomaly (a resource-wide baseline is a poor predictor for any single hour on a resource with a strong daily swing — this was found and fixed during Milestone 3's own testing).

**Why deterministic analytics instead of just asking the LLM?**
Reproducibility, auditability, and cost. A judge (or a real operator) can look at the code and know exactly why a number is what it is. An LLM asked to "detect the anomaly and estimate savings" would produce different numbers on different calls and couldn't be trusted for financial/environmental figures.

**Why use AI at all, then?**
To do what deterministic code is bad at: explaining *why* a pattern is suspicious in plain language, comparing it against alternative explanations, and recommending a next investigative step — reasoning, not arithmetic.

**What exactly does the LLM do?**
It receives a structured evidence packet (already-computed deviation, persistence, context, and ranked candidate causes) and returns a structured explanation: likely cause, observed facts vs. inference, alternative explanations, a recommended next step, and a categorical (not numeric) confidence. It never receives raw telemetry and never computes a number.

**How do you prevent hallucinations?**
Two layers: Pydantic schema validation (shape), then grounding validation (content) — every cited cause must be in the supplied candidate list, every cited evidence signal must be in the supplied evidence list, and every number in the free text must match a number actually present in the evidence packet (within a small tolerance for rounding). Anything that fails either check is discarded, not partially trusted. Verified with 9 adversarial tests that specifically try to smuggle invented percentages, causes, evidence, and savings claims through — all correctly rejected (`tests/hardening/test_ai_grounding_adversarial.py`).

**What happens if the AI fails?**
A deterministic fallback engine builds the identical output structure directly from the same evidence and ranked candidate causes, using template text. It's held to the exact same grounding validation as the AI path — no lower bar. `explanation_source` (`ai` vs. `fallback`) is always recorded and shown honestly in the UI; the fallback is never mislabeled as AI output.

**How do you calculate CO2e?**
`consumption × emission factor`, where the factor comes from a configurable, versioned registry (never hardcoded inline), and the specific factor value/version/source used is snapshotted onto every impact record so a later factor update never retroactively changes a historical figure. Water's factor is explicitly labeled an indirect/embedded-energy estimate, not a direct emission. Default seed values are labeled illustrative pending a finalized citation — see `EMISSION_CALCULATIONS.md`.

**How do you verify savings?**
Two separate comparisons: (1) post-intervention consumption vs. the ordinary contextual baseline — determines whether behavior looks statistically normal again, gated by a minimum-data requirement, and downgraded to lower confidence if the operating context doesn't match the original anomaly's; (2) post-intervention consumption vs. the *counterfactual* (the anomalous rate that was actually observed) — determines the avoided-consumption/cost/CO2e figures. Verified against real telemetry both ways: a genuine fix reaches `VERIFIED`; a deliberately dishonest early completion (still inside the leak window) correctly produces `NO_MEASURABLE_IMPROVEMENT`, not a false positive.

**How does hardware integration work?**
It doesn't yet — this MVP is explicitly software-only, using CSV upload and a deterministic simulator. The ingestion layer is built so a future smart meter, IoT sensor, or BMS feed would write to the same `measurements` table in the same shape, and the entire Intelligence Core downstream would need no changes. This is a documented interface, not a claimed integration.

## Innovation

**What is novel about EcoTwin?**
Not any single technique — the combination of hardware-agnostic ingestion, evidence-first cause investigation with a validated AI-hallucination defense, and first-class post-intervention verification, packaged for a market segment (single-site Indian SMEs) that existing enterprise and hardware-coupled products don't serve well.

**What existing products inspired it?**
Enterprise fault-detection-and-diagnostics platforms (Schneider EcoStruxure) for the diagnostic-reasoning concept, and IoT leak-detection meters (WEGoT) for the anomaly-alerting concept — see `COMPETITIVE_ANALYSIS.md` for the full comparison.

**What does EcoTwin do differently?**
Verification as a first-class, always-visible step rather than implicit ongoing monitoring; a documented, auditable severity/classification methodology instead of a black box; and hardware independence instead of requiring a specific meter brand.

**Why is it scalable?**
The schema is deliberately generic (`Resource`/`Measurement` shared across resource types, not duplicated per type), so adding fuel/waste or additional locations needs no redesign — but this is an architectural claim, not a demonstrated one; the working system has only been exercised against one location's synthetic dataset (see `HACKATHON_READINESS.md`, "Innovation").

## Deployment

**How would you connect smart meters?**
Implement one new ingestion source satisfying the same `NormalizedMeasurement` contract CSV and the simulator already use, writing to the same `measurements` table via the same `bulk_insert_measurements` service function — no change to the Intelligence Core.

**How would this work with a BMS?**
Same answer — a BMS integration would be another ingestion source, not a new analysis pipeline.

**What happens if sensors fail?**
Not built for this MVP. The architecture's cold-start/insufficient-data handling (baselines and verification both explicitly report "insufficient data" rather than fabricating confidence) is the same mechanism that would need to extend to detect a genuinely failed/stuck sensor feed — flagged as future work in `FUTURE_SCOPE.md`, not implemented.

**How would this scale to 1,000 buildings?**
Architecturally, the generic schema and stateless analysis functions don't have an obvious per-building bottleneck, but this has not been load-tested. Multi-tenancy, authentication, and a production database (PostgreSQL, not the SQLite used in this local sandbox) would all be required first — see `TECHNICAL_DEBT.md`.
