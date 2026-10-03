# EcoTwin

**"Find waste. Understand why. Act smarter."**

> EcoTwin is a hardware-agnostic sustainability intelligence platform that detects abnormal electricity and water consumption, investigates likely causes with evidence-backed AI reasoning, recommends corrective actions, and verifies whether those actions actually worked.

Built for **EcoLogic 1.0** (Mercer | Mettl), theme: *"Shape a greener tomorrow."*

---

## ⚠️ Status: Milestone 8 complete — hardened, audited MVP

EcoTwin's full product loop (detect → investigate → recommend → intervene → verify → measure impact) works end-to-end through the actual UI, in one click, deterministically and repeatably — and has been adversarially tested: fabricated AI claims, empty/extreme/malformed telemetry, and intervention/verification edge cases are all confirmed handled correctly, not just documented as handled. The backend remains the sole source of truth for every number and decision — the frontend never recomputes an anomaly score, AI conclusion, or savings figure. See `docs/DEMO.md` for the Quick Demo, Judge Walkthrough, and Technical Demo, and `docs/HACKATHON_READINESS.md` for an honest self-assessment against the judging criteria.

## The core loop

```text
Detect → Investigate → Explain → Recommend → Intervene → Verify → Measure Impact
```

Given electricity and water consumption data, EcoTwin:
1. **Detects** abnormal consumption using a multi-signal statistical baseline (not a single-metric threshold)
2. **Builds evidence** — the same signals that drove detection, shown to the user directly
3. **Investigates** likely causes: deterministic candidate-cause scoring, explained by an AI Reasoning Layer that reasons over the evidence but never invents numbers (falls back to a deterministic engine if the AI is unavailable or its output doesn't validate)
4. **Recommends** a specific corrective action
5. **Verifies**, once enough post-intervention data exists, whether consumption actually returned to normal
6. **Reports** savings clearly labeled as potential, estimated, or verified

## MVP scope

**Resources:** electricity and water only (CO2e derived from both). Fuel/waste are future scope.
**Pages:** Overview, Resources, Anomalies/Investigation, Impact, Data. No separate Recommendations, Interventions, Settings, or Admin pages — those workflows live inside the five above.

## The gap this fills

See `docs/COMPETITIVE_ANALYSIS.md` (includes a full "Novelty Positioning" section). In short: enterprise AI energy platforms (Spacewell, Schneider EcoStruxure/Resource Advisor+, BrainBox AI) serve BMS-equipped, multi-site portfolios; India-market IoT meters (WEGoT, DigitalPaani) are hardware-coupled and alert-only; MSME carbon calculators are static, non-monitoring estimators. None of these combine hardware-agnostic ingestion, evidence-first explainable investigation, and first-class intervention verification for single-site, non-enterprise organizations. This is a recombination of known techniques for an underserved segment, not a claim of inventing new detection science.

## Numerical integrity & verification

Every consumption figure, deviation, severity, cost, and CO2e number comes from deterministic code (`app/analytics/`), never from the AI. The AI (`app/ai/`) only reasons over an evidence packet the deterministic engine already built, and its response is schema- and grounding-validated — any invented cause, evidence reference, or number causes the response to be discarded in favor of an equally-structured deterministic fallback. Verification compares real post-intervention telemetry against the same baseline engine used for detection, with explicit `insufficient_data`/`no_measurable_improvement`/`improvement_detected`/`verified` states — an intervention is never labeled "verified" just because it was marked complete. See `docs/RELIABILITY_AND_TRUST.md` and `docs/AI_ARCHITECTURE.md` for full detail, and `docs/TECHNICAL_DEBT.md`/`docs/HACKATHON_READINESS.md` for an honest account of what's been adversarially tested and what hasn't.

## Documentation index

| Doc | Contents |
|---|---|
| [`docs/COMPETITIVE_ANALYSIS.md`](docs/COMPETITIVE_ANALYSIS.md) | Researched landscape + Novelty Positioning |
| [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture, engine pipeline, folder structure, technical risks |
| [`TECH_STACK.md`](docs/TECH_STACK.md) | Stack choices and justification |
| [`DATA_MODEL.md`](docs/DATA_MODEL.md) | Simplified, generic Resource/Measurement schema |
| [`AI_ARCHITECTURE.md`](docs/AI_ARCHITECTURE.md) | What the AI can/can't do, structured output, validation, fallback |
| [`ANOMALY_DETECTION.md`](docs/ANOMALY_DETECTION.md) | Multi-signal baseline/severity methodology |
| [`EMISSION_CALCULATIONS.md`](docs/EMISSION_CALCULATIONS.md) | CO2e estimation + factor registry |
| [`API.md`](docs/API.md) | REST API design |
| [`ROADMAP.md`](docs/ROADMAP.md) | Phases and milestones |
| [`TESTING.md`](docs/TESTING.md) | Test strategy + scenario validation framework |
| [`DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Deployment plan |
| [`DEMO.md`](docs/DEMO.md) | Full judging demo script with a concrete named scenario |
| [`LIMITATIONS.md`](docs/LIMITATIONS.md) | Known MVP limitations |
| [`LIMITATION_RESOLUTION_MATRIX.md`](docs/LIMITATION_RESOLUTION_MATRIX.md) | Limitation → risk → solution → result for every item |
| [`RELIABILITY_AND_TRUST.md`](docs/RELIABILITY_AND_TRUST.md) | Why EcoTwin stays trustworthy even when the AI fails |
| [`FUTURE_SCOPE.md`](docs/FUTURE_SCOPE.md) | Post-hackathon roadmap |
| [`HACKATHON_READINESS.md`](docs/HACKATHON_READINESS.md) | Honest self-assessment against the judging criteria, with an audited scorecard |
| [`TECHNICAL_DEBT.md`](docs/TECHNICAL_DEBT.md) | What's genuine debt vs. acceptable MVP scope vs. deliberately deferred |
| [`JUDGE_QA.md`](docs/JUDGE_QA.md) | Prepared answers to likely product/technical/innovation/deployment questions |

## Tech stack (summary — see `TECH_STACK.md`)

- **Frontend:** React + Vite + plain CSS (design tokens — see `TECH_STACK.md` for why this replaced the originally planned Tailwind)
- **Backend:** Python + FastAPI
- **Data processing:** pandas, numpy — statistical, explainable anomaly detection, not black-box ML
- **Database:** PostgreSQL
- **AI:** Anthropic API — structured reasoning over evidence only, always with a validated deterministic fallback

## Setup

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DATABASE_URL, ANTHROPIC_API_KEY (optional — app works without it)
uvicorn app.main:app --reload

# Frontend (in a second terminal)
cd frontend
npm install
cp .env.example .env.local   # VITE_API_URL, defaults to http://localhost:8000
npm run dev                   # http://localhost:5173
```

## Running the demo

Open http://localhost:5173, click **"Run EcoTwin Demo"** in the top bar (works even with no data seeded yet — it seeds automatically). See `DEMO.md` for the exact scenario (Greenfield Public School, a water-leak-after-hours anomaly) and the full step-by-step judging script. Command-line equivalent: `python -m app.cli seed-demo --reset && python -m app.cli run-demo` (backend/).

## License / hackathon context

Built for EcoLogic 1.0 (Mercer | Mettl hackathon). Not yet licensed for external reuse pending team decision.
