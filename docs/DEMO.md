# Demo (Revised — Final Scenario)

## Quick Demo (for someone who just wants to run the product)

```bash
# Terminal 1
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload          # http://localhost:8000

# Terminal 2
cd frontend
npm install
cp .env.example .env.local
npm run dev                             # http://localhost:5173
```

1. Open http://localhost:5173
2. Click **Run EcoTwin Demo** in the top bar
3. Wait a few seconds for the single backend workflow call to complete
4. Click **View Investigation**
5. Read the evidence, the investigation reasoning, the recommendation, and the verified impact — all on one page
6. Optionally click **Reset demo and run again from scratch** at the bottom of the completion panel to watch it happen again from a clean state

That's the whole product loop: detect → investigate → recommend → intervene → verify → measure impact, working end to end on real (simulated) telemetry.

## Judge Walkthrough

> **EcoTwin doesn't stop at detecting waste — it closes the loop by investigating the cause, recommending an intervention, and verifying whether the intervention actually worked.**

| Step | What to do | What you'll see |
|---|---|---|
| 1 | Click **Run EcoTwin Demo** | A short, honest loading state (the backend does this in one call — no fake staged animation), then a completion summary |
| 2 | Read the completion summary | Severity, likely cause, deviation, duration, building status, occupancy — then recommended inspection, intervention completed, and verified impact, all real numbers |
| 3 | Click **View Investigation** | Lands directly on the investigated water anomaly — no searching required |
| 4 | Look at the evidence | Plain-language, evidence-first: "Consumption was over 1,000% above the expected baseline," "Building was marked closed," "Occupancy was zero," shown prominently, not hidden |
| 5 | Read "How EcoTwin reached this conclusion" | Deterministic analysis (baseline, deviation, persistence, context, candidate causes) shown side-by-side with the AI's reasoning (likely cause, alternatives, recommended next step) — makes the architecture legible without reading code |
| 6 | Read the contextual investigation | The engine label honestly says "Deterministic fallback" or "AI reasoning" depending on whether an API key is configured — never claims AI when it wasn't used |
| 7 | Look at the investigation timeline | A vertical timeline confirms each stage — detected, evidence collected, cause investigated, action recommended, intervention completed, improvement verified |
| 8 | Review the before/after chart | Real telemetry around the anomaly and intervention point, not a decorative graph |
| 9 | Review verified impact | Avoided consumption, ₹ financial impact, kg CO2e — clearly labeled `verified`, distinguished from the earlier `estimated` figure shown before the intervention |
| 10 | Return to Overview | The KPI row and recent-impact section reflect what just happened |

**Timing:** roughly 3-4 minutes total — see "Hackathon demo timing" below.

## Technical Demo (for judges who want the mechanism, not just the result)

Everything the UI shows traces to a specific deterministic or AI component:

- **Simulator** (`app/ingestion/telemetry_simulator.py`, `scenarios.py`) — deterministic, seeded synthetic telemetry with realistic daily/weekly patterns; the anomaly is discovered, never hardcoded.
- **Deterministic analytics** (`app/analytics/`) — causal baseline engine, deviation/z-score calculation, persistence detection, a documented point-based severity/classification system, evidence generation, candidate-cause ranking, cost/CO2e calculations. None of this involves an LLM.
- **AI Reasoning Layer** (`app/ai/`) — receives only the evidence packet the deterministic engine already built, returns a structured, schema- and grounding-validated explanation, or transparently falls back to a deterministic template if the AI is unavailable or its response doesn't validate.
- **Intervention + Verification** (`app/services/intervention_service.py`, `verification_service.py`) — a simple 3-state action lifecycle, kept strictly separate from a 5-state verification outcome that reuses the exact same baseline engine (no second methodology) plus a counterfactual comparison for the avoided-consumption figure.
- **Frontend** (`frontend/src/`) — a presentation layer only; every number, evidence item, AI conclusion, and verification state is fetched from the backend and rendered as-is.

See `ARCHITECTURE.md`, `ANOMALY_DETECTION.md`, `AI_ARCHITECTURE.md`, and `RELIABILITY_AND_TRUST.md` for full detail on each layer.

## Hackathon demo timing (~3-4 minutes)

| Time | What to say/do |
|---|---|
| 0:00-0:30 | Introduce EcoTwin: a hardware-agnostic sustainability intelligence platform that closes the loop from anomaly detection to verified impact. |
| 0:30-1:30 | Click Run EcoTwin Demo, narrate the completion summary (severity, cause, evidence highlights) while it loads. |
| 1:30-2:30 | Open the investigation. Point at the evidence list and the deterministic-vs-AI split — this is the "not just a weird number" moment. |
| 2:30-3:30 | Point at the intervention/verification section and the before/after chart — the verified, not just estimated, impact. |
| 3:30-4:00 | Show the Impact page's estimated-vs-verified distinction and close with the "closes the loop" line above. |

---

## Building context (fixed for the demo)

**Location:** "Greenfield Public School" — a single-site campus in Jaipur, Rajasthan, with one administrative building tracked by EcoTwin.
**Resources tracked:** electricity (main building meter) and water (second-floor washroom line).
**Operating hours:** Mon–Fri, 08:00–18:00. Closed weekends and after 18:00.
**Data:** 10 weeks of deterministic simulated telemetry at 1-hour resolution, generated once and checked into `data/demo_scenarios/` for reproducibility (same output every run — not regenerated randomly at demo time).

## Normal behavior (baseline weeks 1–9)

- **Electricity**: diurnal curve rising from ~08:00, peaking midday, falling after 17:00; weekday pattern distinct from a flat, low weekend pattern; small realistic noise.
- **Water**: similar diurnal curve tied to occupancy (peaks around breaks/lunch), dropping to near-zero after 18:00 and on weekends.

## The anomaly (week 10, Wednesday)

At 18:00 — closing time — water consumption, which normally drops to near-zero, **remains elevated** and stays elevated through 21:00 (the last hour before the next day's data begins), while `operating_status = closed` and `occupancy = 0`. The shape is flat and sustained (not a single spike), consistent with continuous unattended flow.

## Evidence shown to the user (deterministic, drives both UI and AI input)

- Deviation: +238% vs. baseline for that hour/weekday slot
- Operating status: closed
- Occupancy: 0
- Duration: 3 hours sustained elevation
- Pattern: flat/continuous, not a short burst
- Classification: `operationally_suspicious`, severity `HIGH`

## Candidate causes (deterministic ratings)

- `plumbing_leak` — high
- `irrigation_left_active` — medium (the school has a small irrigation line on the same meter branch)
- `metering_anomaly` — low

## AI reasoning (or fallback, both demonstrable)

The AI Reasoning Layer receives exactly the evidence above and returns a structured explanation naming `plumbing_leak` as the likely cause, citing the closed/zero-occupancy/sustained/flat signals as support, `irrigation_left_active` as the primary alternative, and suggesting the operator first check whether the irrigation controller had an active schedule during that window (see `AI_ARCHITECTURE.md` for the exact schema). With the AI key removed, the deterministic fallback engine produces an equivalent structured explanation from the same evidence and rule-based cause ranking — this should be demonstrated live if time allows, to prove the core workflow doesn't depend on the AI API being up.

## Recommended action

"Inspect the second-floor washroom flush valve and supply line for a continuous leak; confirm the irrigation controller's schedule is off for this window."

## Intervention

Judge/demo user clicks **Mark Intervention Complete**.

## Post-intervention behavior (simulated)

The next 24 hours of simulated telemetry (deterministically generated as part of the same fixed dataset, not randomly re-rolled) show water consumption returning to the normal after-hours near-zero pattern.

## Verification

The Verification Engine compares the post-intervention window against the same baseline slot used to detect the anomaly. Deviation drops below the "unusual" threshold and stays there for the full minimum verification window → **verified improvement**.

## Verified impact shown

- Consumption reduction: quantified from the actual pre/post delta over the observed window
- Estimated cost saved (₹): consumption delta × configured water cost factor
- CO2e avoided (kg): consumption delta × configured water emission factor (labeled as an indirect/embedded estimate — see `EMISSION_CALCULATIONS.md`)
- Clearly labeled **verified**, not potential or estimated, because the minimum post-intervention data gate was met

## Demo flow (RUN ECOTWIN DEMO → VERIFIED IMPACT)

| Step | Action | UI state |
|---|---|---|
| 1 | Click **Run EcoTwin Demo** | Overview loads with the 10-week Greenfield School dataset |
| 2 | Automatic analysis | Anomaly appears on Resources/Overview: "High water consumption — Wed, week 10" |
| 3 | Open investigation | Evidence list shown (deviation, closed, zero occupancy, duration, pattern) |
| 4 | Candidate causes shown | plumbing_leak (high), irrigation_left_active (medium), metering_anomaly (low) |
| 5 | AI reasoning runs | Structured explanation + distinguishing check displayed |
| 6 | Recommendation shown | Inspect flush valve / confirm irrigation schedule |
| 7 | Click **Mark Intervention Complete** | Status → pending verification |
| 8 | Post-intervention data loads (pre-generated, deterministic) | — |
| 9 | Verification runs automatically | Status → verified improvement |
| 10 | Impact page | Verified consumption reduction, ₹ saved, kg CO2e avoided |

Target runtime: under 4 minutes live. Fallback: pre-recorded video + static screenshots of each step, per the hackathon's required submission assets.

## Judge talking points to hit live

- The anomaly math and cost/CO2e figures are deterministic — point at `ANOMALY_DETECTION.md`/`EMISSION_CALCULATIONS.md` if asked "is this real math or an LLM guessing."
- The AI only reasons over evidence already computed — offer to re-run the investigation with the AI key removed to show the fallback engine producing an equivalent structured explanation.
- The potential/estimated/verified distinction on the Impact page is a deliberate honesty feature.
- The ingestion layer is hardware-agnostic — the same intelligence core would run unchanged on a real smart meter feed; the simulator/CSV are today's data sources, not a hardware claim.

## Implementation notes (Milestone 4)

The AI reasoning step described above is now real. Run it directly against the actual Greenfield Public School dataset with:

```bash
cd backend
python -m app.cli seed-demo --reset
python -m app.cli investigate-demo
```

With no `ANTHROPIC_API_KEY` configured (this sandbox's normal state), the command reports `AI Reasoning Layer: disabled` up front, then produces the full investigation via the deterministic fallback engine — labeled honestly as `FALLBACK`, not disguised as AI output. Actual output against the real dataset:

```text
Explanation source: FALLBACK
(AI unavailable — deterministic fallback used. Reason: ANTHROPIC_API_KEY is not configured.)

Likely cause: plumbing_leak
Reasoning confidence: high

Observed:
  - Consumption was 1300% above the expected baseline for this time slot.
  - The elevated reading persisted for 3 hour(s) (3 consecutive readings), not a single spike.
  - The location was marked closed for most of this window.
  - Recorded occupancy was zero for most of this window.
  - Classified as operationally suspicious: unusual, persistent, and inconsistent with expected operating context.

Inference:
  The available evidence — baseline deviation, persistence, operating status, occupancy, classification —
  is most consistent with a continuous, unattended water leak, which the deterministic engine rated
  'high' confidence based on these signals.

Alternative explanations:
  - irrigation_left_active: Rated 'medium' confidence by the deterministic engine — less consistent
    with the observed signals than a continuous, unattended water leak.
  - metering_anomaly: Rated 'low' confidence by the deterministic engine — less consistent with the
    observed signals than a continuous, unattended water leak.

Recommended next step:
  Inspect fixtures, toilets, and the incoming water line for continuous flow, starting with the
  areas nearest this meter.
```

Note the deviation shown here (1300%) is higher than the illustrative 238% used earlier in this document's narrative sketch — that number was always illustrative; the real simulator's closed-hours baseline for water is very close to zero, so a real injected leak reads as a very large percentage above it. This is expected and is itself good evidence: see `ANOMALY_DETECTION.md`'s discussion of why a near-zero baseline mean produces large but honest percentages.

With a real `ANTHROPIC_API_KEY` configured, the same command instead calls the Anthropic API and, if the response passes schema and grounding validation, reports `Explanation source: AI` with a natural-language version of the same evidence-grounded conclusion. This path is exercised by 13 automated tests using a mocked provider (`tests/ai/`), since this sandbox has no real API key to demonstrate it live end-to-end.

Via the API: `POST /api/anomalies/{id}/investigate` performs the same flow — see `API.md`.

## Implementation notes (Milestone 5)

The full closed loop — detect → investigate → recommend → intervene → verify → measure — is now real. Run it end to end with a single command against the actual Greenfield Public School dataset:

```bash
cd backend
python -m app.cli seed-demo --reset
python -m app.cli run-demo
```

Actual output against the real dataset:

```text
Location: Greenfield Public School (<uuid>)
Anomaly: high severity, id=<uuid>
Investigation: plumbing_leak (source: fallback)
Recommendation: Inspect fixtures, toilets, and the incoming water line for continuous flow,
  starting with the areas nearest this meter.
Intervention: <uuid>

Verification status: VERIFIED
  Post-intervention consumption is back within the normal expected range, backed by a
  sufficient-confidence baseline and matching operating context.

Avoided consumption: 39.11
Money saved: 1.96
CO2e avoided: 0.014 kg
```

Running the same command again reuses the existing anomaly, investigation, recommendation, and intervention rather than duplicating them (idempotent — see `LIMITATION_RESOLUTION_MATRIX.md`), and re-verification is cheap to recompute since it's pure deterministic arithmetic over current telemetry.

**Honesty check, verified with real data:** completing the intervention *during* the leak (a dishonest completion timestamp) rather than after it correctly produces `NO_MEASURABLE_IMPROVEMENT`, not a false `VERIFIED` — the system doesn't just always say yes once an intervention is marked complete.

Via the API, the same flow is `POST /api/anomalies/{id}/investigate` → `POST /api/investigations/{id}/interventions` → `POST /api/interventions/{id}/complete` → `POST /api/interventions/{id}/verify`, or the single orchestrated `POST /api/demo/run` — see `API.md`.

## Running the demo from the actual UI (Milestone 6)

1. `cd backend && uvicorn app.main:app --reload` (port 8000)
2. `cd frontend && npm run dev` (port 5173)
3. Open http://localhost:5173 — the Overview page loads (empty state if no data yet)
4. Click **Run EcoTwin Demo** in the top bar
5. The backend seeds the Greenfield Public School dataset if needed, runs the full detect → investigate → recommend → intervene → verify loop, and the modal shows the completed step list plus a summary (likely cause, verification status, avoided consumption/cost/CO2e)
6. Click **View Investigation** to land directly on the investigated anomaly, with evidence, the AI/fallback reasoning (honestly labeled), the recommendation, and the intervention/verification result all visible on one page

This is the same backend workflow validated via `python -m app.cli run-demo` (see "Implementation notes (Milestone 5)" above) — the frontend adds no logic of its own, only a progress display and the resulting page.

## Implementation notes (Milestone 7)

- **Demo reset, scoped.** `POST /api/demo/reset` (and `python -m app.cli reset-demo`) fully clears one named location's data — measurements, baselines, anomalies, investigations, recommendations, interventions, impact records, resources, and the location itself — so the next `/demo/run` starts genuinely fresh. Scoped to that one location only; never touches any other location's data. Verified manually: reset then re-run produces a new anomaly/intervention ID with the identical deterministic story (same deviation, cause, verification outcome, avoided consumption).
- **Demo result enriched.** `POST /api/demo/run`'s response now also includes `resource_type`, `deviation_pct`, `z_score`, `persistence_hours`, `majority_closed`, and `majority_zero_occupancy` — all already-computed fields from the anomaly's signals, simply surfaced so the frontend's completion screen can show building status/occupancy/deviation/duration without an extra round-trip or reconstructing anything client-side.
- **Investigation timeline, methodology split, and before/after chart** are new frontend-only components (`InvestigationTimeline`, `MethodologySplit`, `VerificationChart`) — each purely presentational, deriving every displayed value from data the backend already returns. No new backend business logic was introduced for these.
- **Repeated-demo behavior confirmed manually 3x** against real running servers (not just the CLI): fresh seed → run → idempotent re-run (same anomaly/intervention IDs, same verified outcome) → reset → fresh run again (new IDs, same deterministic story).

## Final Demo Repetition (Milestone 8)

`POST /api/demo/run` called 5 times in one session against real running servers, with `POST /api/demo/reset` in between runs 3 and 4:

| Run | Status | Severity | Cause | Deviation | Verification | Avoided | Money Saved | CO2e |
|---|---|---|---|---|---|---|---|---|
| 1 (fresh seed) | complete | high | plumbing_leak | +1299.62% | verified | 39.108 | ₹1.96 | 0.0140 kg |
| 2 (idempotent) | complete | high | plumbing_leak | +1299.62% | verified | 39.108 | ₹1.96 | 0.0140 kg |
| 3 (idempotent) | complete | high | plumbing_leak | +1299.62% | verified | 39.108 | ₹1.96 | 0.0140 kg |
| — reset — | | | | | | | | |
| 4 (fresh after reset) | complete | high | plumbing_leak | +1299.62% | verified | 39.108 | ₹1.96 | 0.0140 kg |
| 5 (idempotent) | complete | high | plumbing_leak | +1299.62% | verified | 39.108 | ₹1.96 | 0.0140 kg |

Every meaningful deterministic value is bit-for-bit identical across all 5 runs, including immediately after a full scoped reset — confirming both the simulator's seeded determinism (Milestone 2) and the full detect→verify pipeline's reproducibility hold under repeated real execution, not just in isolated unit tests.
