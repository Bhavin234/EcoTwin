# Architecture (Revised)

## System diagram

```text
                         ┌───────────────────────────┐
                         │          FRONTEND           │
                         │   React + Vite + plain CSS │
                         │  Overview · Resources ·      │
                         │  Anomalies/Investigation ·    │
                         │  Impact · Data                │
                         └──────────────┬───────────────┘
                                        │ REST (JSON)
                         ┌──────────────▼───────────────┐
                         │          BACKEND API           │
                         │        FastAPI (Python)        │
                         └──────────────┬───────────────┘
                                        │
        ┌───────────────────────────────┼────────────────────────────────┐
        │                                │                                │
┌───────▼─────────┐          ┌───────────▼───────────┐          ┌─────────▼─────────┐
│ TELEMETRY         │          │  ECOTWIN INTELLIGENCE   │          │   PERSISTENCE       │
│ INGESTION LAYER    │─────────▶  CORE (deterministic)   │◀────────▶│   PostgreSQL         │
│ CSV / Simulator /  │          │  agents as modules       │          │                     │
│ future IoT/BMS      │          └───────────┬───────────┘          └─────────────────────┘
└─────────────────────┘                      │
                                    ┌─────────▼──────────┐
                                    │  AI REASONING LAYER  │
                                    │  Claude API — reasons │
                                    │  over evidence only;   │
                                    │  never computes numbers │
                                    │  Falls back to           │
                                    │  deterministic engine     │
                                    └───────────────────────────┘
```

## Component responsibilities

**Telemetry Ingestion Layer** — a single interface (`fetch_new_measurements()`) implemented by three sources for the MVP: CSV upload, deterministic demo/scenario simulator, and a manual/API push endpoint (standing in for a future live IoT/smart-meter feed). All sources write to the same `measurements` table in the same shape. The Intelligence Core never knows or cares which source produced a row — this is what makes the architecture hardware-agnostic, not a hardware claim (we are not building or simulating physical devices, only the data contract a real device would eventually satisfy).

**EcoTwin Intelligence Core (deterministic)** — six responsibilities, implemented as Python modules/functions inside one FastAPI service (not microservices, not an orchestration framework):

```text
RESOURCE DATA
    │
    ▼
[Data Agent]            validate, normalize, flag missing/malformed values
    │
    ▼
[Baseline Engine]       rolling mean/std per (resource, hour-of-day, day-of-week)
    │
    ▼
[Anomaly Engine]        multi-signal scoring → severity (LOW/MEDIUM/HIGH/CRITICAL)
    │
    ▼
[Evidence Builder]      turns raw signals into a structured, human-legible evidence list
    │
    ▼
[Investigation Engine]  deterministic candidate-cause scoring (rule-based)
    │            │
    │            ▼
    │      [AI Reasoning Layer]   reasons over evidence + candidate scores,
    │                             returns structured explanation (see AI_ARCHITECTURE.md)
    │            │
    ▼            ▼
[Impact Engine]         wastage, cost, CO2e — always deterministic
    │
    ▼
[Recommendation Engine] cause → prioritized action (rule lookup, AI may rephrase)
    │
    ▼
USER ACTION (mark intervention complete)
    │
    ▼
[Verification Engine]   deterministic pre/post comparison, potential/estimated/verified savings
```

**AI Reasoning Layer** — receives only the structured evidence and deterministic candidate-cause scores already computed above; returns structured reasoning (likely cause, reasoning, supporting evidence references, alternative causes, recommended next observation/action). It cannot alter or introduce numbers. If it fails, times out, or returns invalid/unparseable output, the system falls back to a deterministic rule-based investigation engine that produces the same structural output from the same evidence, so the workflow is never blocked. Full detail in `AI_ARCHITECTURE.md` and `RELIABILITY_AND_TRUST.md`.

## Revised page set (reduced scope)

Only five pages/workflow areas, matching the reduced MVP scope:

1. **Overview** — top-level metrics, active issues, trend snapshot.
2. **Resources** — electricity and water consumption, baselines, and anomalies list.
3. **Anomalies / Investigation** — the central workflow: anomaly → evidence → candidate causes → AI reasoning → recommended action → mark intervention complete → verification, all on one investigation view (no separate Recommendations/Interventions pages).
4. **Impact** — potential / estimated / verified savings, cost, CO2e.
5. **Data** — view ingested telemetry, upload CSV, run the demo/scenario simulator.

No separate Settings, AI Assistant, or Administration pages for the MVP; emission-factor configuration is a small panel inside Data or Impact rather than a standalone page.

## Revised folder structure

```text
eco/
├── README.md
├── ARCHITECTURE.md
├── TECH_STACK.md
├── DATA_MODEL.md
├── AI_ARCHITECTURE.md
├── ANOMALY_DETECTION.md
├── EMISSION_CALCULATIONS.md
├── API.md
├── ROADMAP.md
├── TESTING.md
├── DEPLOYMENT.md
├── DEMO.md
├── LIMITATIONS.md
├── LIMITATION_RESOLUTION_MATRIX.md
├── RELIABILITY_AND_TRUST.md
├── FUTURE_SCOPE.md
├── docs/
│   └── COMPETITIVE_ANALYSIS.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                     # routers: resources, measurements, anomalies,
│   │   │                            # investigations, impact, demo
│   │   ├── engine/                  # data_agent, baseline_engine, anomaly_engine,
│   │   │                            # evidence_builder, investigation_engine,
│   │   │                            # impact_engine, recommendation_engine,
│   │   │                            # verification_engine
│   │   ├── ai/                      # ai_client.py, prompt templates, response
│   │   │                            # validation (pydantic schema), fallback engine
│   │   ├── models/                  # SQLAlchemy ORM
│   │   ├── schemas/                 # Pydantic request/response
│   │   ├── ingestion/               # csv_source.py, telemetry_simulator.py
│   │   └── core/                    # config, db session
│   ├── tests/
│   │   └── scenarios/               # normal / leak / overconsumption / closed-building /
│   │                                 # legit-spike / post-intervention scenario fixtures
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                   # Overview, Resources, Investigation, Impact, Data
│   │   ├── components/
│   │   ├── api/
│   │   └── App.tsx
│   └── .env.example
└── data/
    └── demo_scenarios/               # generated CSVs per scenario (checked in for reproducibility)
```

## Technical risks (revised)

1. **Telemetry realism** — the simulator must produce plausible daily/weekly patterns and evidence-rich anomalies (not a single spike row); mitigated by building a proper generator (see `DEMO.md`) rather than manually fabricated rows.
2. **AI reasoning going out of bounds** — mitigated by strict structured-output schema validation; any response that doesn't validate is discarded in favor of the deterministic fallback (`AI_ARCHITECTURE.md`).
3. **Anomaly threshold tuning across two different resource types** (electricity, water) with different noise characteristics — mitigated by resource-specific baseline parameters, not one global threshold.
4. **Verification timing** — needing enough post-intervention data before claiming "verified" — mitigated by an explicit minimum-data gate (see `ANOMALY_DETECTION.md`/`RELIABILITY_AND_TRUST.md`); the demo scenario is built so this gate is met within the simulated timeline.
5. **Scope creep back toward the original 8-page design** — mitigated by this document being the source of truth for the reduced 5-area page set.

## Frontend architecture (Milestone 6, implemented)

**Deviation from the original plan: plain CSS instead of Tailwind.** `TECH_STACK.md` originally named Tailwind as preferred. Milestone 6's actual instructions allow "standard CSS or a lightweight styling approach," and building the specific, restrained enterprise look the brief calls for (explicitly *not* a generic templated look) was more directly achievable with hand-written CSS custom properties (design tokens) than with Tailwind's utility classes, without adding a PostCSS build step. No other stack deviation: React + Vite, no Redux/Next.js/UI framework, no charting library (see below).

**No charting library.** Rather than add Recharts (or similar) as a dependency, trend/verification charts are a small hand-rolled SVG component (`src/components/charts/TrendChart.jsx`) — the datasets involved (a few dozen to a few hundred points) don't need a full charting library, and hand-rolling gives full control over the plain, non-decorative look the brief requires.

```text
frontend/
├── src/
│   ├── api/                  client.js (base fetch/error handling), telemetry.js,
│   │                         analytics.js, workflow.js (investigation/intervention/demo)
│   ├── components/
│   │   ├── layout/           Sidebar, TopBar, AppShell, DemoRunner
│   │   ├── charts/           TrendChart (hand-rolled SVG)
│   │   ├── common/           StatusBadge, States (loading/error/empty/AI-unavailable), Primitives (Card/Button/MetricTile)
│   │   ├── anomalies/        AnomalyTable
│   │   ├── investigations/   EvidenceList, AIInvestigationPanel, RecommendationPanel, InterventionFlow
│   │   └── impact/           ImpactSummary
│   ├── pages/                Overview, Resources, Investigations, InvestigationDetail, Impact, Data
│   ├── context/              LocationContext (fetches locations, holds the selected one app-wide)
│   ├── hooks/                useAsync (shared loading/error/data fetching)
│   ├── utils/                format.js (currency/consumption/CO2e/percent/timestamp/duration formatting)
│   ├── styles/                tokens.css (design tokens), pages.css (shared page layout)
│   └── test/                  vitest + Testing Library component/integration tests, mocks.js
```

**No business logic duplicated in the frontend.** Every anomaly score, evidence item, AI/fallback explanation, recommendation, intervention status, verification outcome, and impact figure is fetched from the backend and rendered as-is — the frontend never recomputes a deviation, severity, cause ranking, or savings figure. Two small, deliberate backend additions were made *specifically to avoid* the frontend having to reconstruct backend logic in JavaScript:

1. **`GET /api/resources/{id}/baselines`** — read-only access to persisted baseline snapshots, so "current vs. baseline" on the Resources page doesn't require recomputing a baseline client-side.
2. **`evidence` added to `GET /api/anomalies/{id}`** — the evidence list was previously only reachable internally (via `app.analytics.evidence.evidence_from_signals`, used by the AI evidence packet); it's now included directly in the anomaly detail response so the frontend displays the exact same evidence structure the AI reasoned over, rather than reconstructing it from raw `signals`.
3. **`intervention` nested under `RecommendationOut`** — so the investigation detail page can tell in one request whether an intervention already exists, rather than needing a separate "does this exist" call (which would otherwise require either an extra round-trip or an implicit create-on-view).

See `API.md` for the full endpoint list including these additions.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local   # set VITE_API_URL if the backend isn't on localhost:8000
npm run dev                   # http://localhost:5173
npm run build                 # production build
npm test                       # vitest component/integration tests (no backend required — API calls are mocked)
```

Run both together for the full product: start the backend (`uvicorn app.main:app --reload`, port 8000) and the frontend (`npm run dev`, port 5173) — CORS is already configured for `http://localhost:5173` by default (`backend/.env.example`).

## Judging experience layer (Milestone 7)

Three new, purely presentational frontend components turn the existing backend workflow into a legible judging story, adding no new business logic:

- **`InvestigationTimeline`** — a vertical timeline whose "done"/"pending" state per stage is derived directly from whether `anomaly.evidence`, `investigation.explanation`, `investigation.recommendation`, and `intervention.status`/`verification_status` are present — a visualization of existing state, not a new workflow.
- **`MethodologySplit`** — a side-by-side "Deterministic analysis" vs. "AI contextual investigation" panel, making the core architectural principle (numbers from statistics, reasoning from AI) visible to a non-technical judge without reading code.
- **`VerificationChart`** — a real-telemetry before/after chart spanning from before the anomaly through the post-intervention window, with markers at the anomaly start and the intervention point; if telemetry for the range isn't available, it says so rather than drawing invented data.

One small, scoped backend addition supports the "watch it happen again from scratch" judging need: `reset_demo_location()` (`app/services/demo_service.py`) fully clears one named location's data so a subsequent `/demo/run` reseeds and reanalyzes genuinely fresh, without a destructive whole-database wipe and without touching any other location.
