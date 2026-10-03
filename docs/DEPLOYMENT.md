# Deployment (unchanged approach, re-confirmed)

## Default plan (not mandatory — simplest reliable option)

| Component | Platform | Notes |
|---|---|---|
| Frontend | Vercel | Static build from `frontend/`, `VITE_API_URL` env var |
| Backend | Render or Railway | FastAPI app; `DATABASE_URL` + `ANTHROPIC_API_KEY` (optional) as env vars |
| Database | Managed Postgres (paired with backend host, e.g. Render/Railway/Neon/Supabase) | Run Alembic migrations on deploy |

## Environment variables

`backend/.env.example`:
```text
DATABASE_URL=postgresql://user:password@host:5432/ecotwin
ANTHROPIC_API_KEY=            # optional — app runs in fallback mode if unset
EMISSION_FACTOR_REGION=IN
ENV=production
```

`frontend/.env.example`:
```text
VITE_API_URL=https://ecotwin-api.example.com
```

## Deploy checklist

1. Provision managed Postgres, run migrations, seed `cost_factors`/`emission_factors` with cited defaults.
2. Deploy backend, confirm `/docs` and `/api/resources` respond against the empty/seeded DB.
3. Deploy frontend pointed at the backend URL.
4. Run `/demo/run` against the deployed environment, confirm the full detect → verify loop works.
5. Re-run `/demo/run` with `ANTHROPIC_API_KEY` unset in the deployed environment to confirm the fallback path also works in production, not just locally.

## Never

- Never commit `.env` files.
- Never put `ANTHROPIC_API_KEY` or `DATABASE_URL` in frontend code or the Vite build — the frontend only ever talks to our own backend.
