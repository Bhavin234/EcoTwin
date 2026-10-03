# Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Vite + plain CSS (design tokens) | Fast dev loop, huge ecosystem, no unnecessary UI framework overhead. **Revised from the original plan (Tailwind)** during Milestone 6 implementation: hand-written CSS custom properties gave more direct control over the specific, restrained enterprise look the brief calls for, without a PostCSS build step — see `ARCHITECTURE.md`, "Frontend architecture" for the full rationale. |
| Backend | Python + FastAPI | Async, typed (Pydantic), auto-generates OpenAPI docs (satisfies API.md requirement almost for free), and Python's data ecosystem (pandas/numpy) is the same language as the anomaly-detection code — no cross-language serialization overhead between "backend" and "data science." |
| Data processing | pandas, numpy, (scikit-learn only if genuinely needed) | Rolling means/std, resampling, z-scores are native pandas operations. We deliberately avoid pulling in scikit-learn models for the MVP baseline detector — statistical thresholds are simpler, explainable to a judge, and easier to defend under "Documentation Quality." |
| Database | PostgreSQL | Relational structure fits the entity model well (organizations → locations → resources → measurements → anomalies → investigations → recommendations → interventions → impact_records); window functions support baseline queries directly in SQL if needed. |
| AI / LLM | Anthropic API (Claude), called only from the AI Reasoning Layer inside the Investigation Engine | Reasons over a structured evidence packet + deterministic candidate-cause scores to produce a structured, validated explanation — never computes anomaly math, cost, CO2e, or confidence scores itself. Always has a schema-validated deterministic fallback (see `AI_ARCHITECTURE.md`, `RELIABILITY_AND_TRUST.md`). |
| Auth | Simple seeded demo-account auth (session/JWT) | No enterprise SSO/RBAC for the MVP — explicitly out of scope per brief; documented as a `FUTURE_SCOPE.md` item. |
| Deployment | Frontend → Vercel, Backend → Render/Railway, DB → managed Postgres (same provider as backend, or Supabase/Neon) | Cheapest reliable path to a public demo URL a judge can open without setup. Not mandatory — documented as the default, swappable if constraints change. |
| Testing | pytest (backend), Vitest/React Testing Library (frontend, if time allows) | Lightweight, standard, no exotic tooling. |

## Explicitly avoided

- No microservices, message queues, or agent-orchestration frameworks for the MVP (agents are Python modules/functions inside one FastAPI service) — avoids operational complexity with no judging benefit.
- No heavyweight ML anomaly models (LSTM/autoencoders) for MVP baseline detection — statistical thresholds are explainable, fast, and sufficient at this data scale; documented as a `FUTURE_SCOPE.md` upgrade path if judges want to see ML sophistication.
- No blockchain, gamification, social features, or chat-as-a-feature — explicitly out of scope per brief.
- No frontend state-management library beyond React's built-in state/query hooks unless the dashboard's data-fetching complexity genuinely requires one (e.g., TanStack Query for caching API calls) — decide during Milestone 9, not upfront.
