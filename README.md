# Career Intelligence Agent + Career Radar Dashboard (MVP+)

## What this build improves
This iteration hardens the original MVP with stronger explainable scoring, an actionable signal layer, scheduler observability, and more reliable SSE UX while preserving the same stack and local workflow.

## Architecture
- **Backend**: FastAPI + SQLAlchemy + Alembic + APScheduler (`/backend`)
- **Frontend**: Next.js + TypeScript + Tailwind (`/frontend`)
- **DB**: PostgreSQL via Docker Compose
- **Realtime**: SSE (`/api/v1/events/stream`) with event ids + heartbeat + frontend reconnect state.
- **Adapters**: External job sources use connector adapters; strategy engine defaults deterministic and can switch via feature flag.

## Core capabilities
- Structured profile engine with seeded senior ops/governance/security persona.
- Opportunity ingest (manual, CSV, mock connectors), CRUD, status updates.
- Explainable scoring engine with weighted factors:
  - profile alignment
  - compensation fit
  - geography fit
  - leadership/seniority fit
  - industry fit
  - strategic value
  - ease of absorption
- Signal layer for opportunities/companies (`new_role_posted`, `comp_below_threshold`, `stale_opportunity`, `high_strategic_visibility`).
- Network intelligence + top entry-point recommendations.
- Weekly micro-actions + monthly strategy reviews.
- Background automation (ingest/rescore/strategy/stale checks).
- Job observability via persisted `job_runs` history and admin UI.

## Scheduler behavior
APScheduler starts on backend startup and runs:
- ingest: every 30m
- rescore: every 20m
- strategy: every 60m
- stale check/signals: every 6h

Each run writes `job_runs` with status, processed count, timestamps, and summary. You can inspect via:
- API: `GET /api/v1/admin/jobs/runs`
- UI: `/admin`
- Manual trigger: `POST /api/v1/admin/jobs/{ingest|rescore|strategy|stale}`

## SSE behavior
SSE is used (instead of WebSockets) for simple one-way dashboard refreshes and lower operational complexity.
- Backend emits `id`, `data`, `retry`, and heartbeat comments.
- Frontend deduplicates events by version and reconnects automatically.
- UI shows realtime connection status badge.

## Local run
```bash
cp .env.example .env
make up
```

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs

## Useful commands
```bash
make migrate
make test-backend
make test-frontend
make logs
make down
```

## Seed data
On first backend startup, seed inserts:
- sample transition profile
- default scoring weights
- feature flags
- sample company + network node
- seeded opportunity (pre-scored)
- initial signals

## Known limitations / next steps
- LLM strategy path currently reuses deterministic output when no provider integration is configured.
- Auth/multi-user tenancy not implemented in v1.
- Network view uses structured panel; graph visualization can be added later.
