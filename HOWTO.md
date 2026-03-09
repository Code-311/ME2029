# HOWTO: Run and Operate Career Radar MVP

## 1) Prerequisites
- Docker + Docker Compose (recommended)
- Or local runtimes:
  - Python 3.12+
  - Node.js 18+
  - PostgreSQL 16+

## 2) Environment variables and configuration
Backend settings are defined in `backend/app/core/config.py` and loaded from `.env`.

Common values:
- `DATABASE_URL` (default: `postgresql+psycopg://postgres:postgres@db:5432/career_radar`)
- `USE_LLM_STRATEGY` (default `false`; MVP runs deterministic mode)
- `API_PREFIX` (default `/api/v1`)
- `CORS_ORIGINS` (default `*`)

Frontend uses:
- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`)

When using Docker Compose, these are already wired in `docker-compose.yml`.

## 3) Start with Docker Compose (recommended)
```bash
make up
```
This starts:
- `db` (Postgres)
- `backend` (FastAPI)
- `frontend` (Next.js)

URLs:
- Frontend: http://localhost:3000
- Backend OpenAPI docs: http://localhost:8000/docs

Stop:
```bash
make down
```

## 4) Run backend/frontend locally without Docker
### Backend
```bash
cd backend
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

## 5) Migrations and seed data
- Apply migrations:
```bash
make migrate
```
or `cd backend && alembic upgrade head`.

- Seed data runs on backend startup in `app.main.startup_event()` via `app.db.seed.seed_data`.

## 6) Scheduler behavior and cadence
Configured in `backend/app/jobs/scheduler.py`:
- ingest: every 30m
- rescore: every 20m
- strategy: every 60m
- stale check/signals: every 6h
- company intelligence: every 45m
- decision engine refresh: every 30m

`job_runs` captures status, count, and summary for observability.

## 7) Connector configuration and manual trigger
Opportunity connector ingest (mock connectors in MVP):
- `POST /api/v1/ingest/connectors`

CSV ingest:
- `POST /api/v1/ingest/csv`

Admin job trigger endpoint:
- `POST /api/v1/admin/jobs/{job_name}`
- supported: `ingest`, `rescore`, `strategy`, `stale`, `company_intelligence`, `decision_engine`

## 8) Company intelligence trigger path
- Ingest endpoint: `POST /api/v1/ingest/company-intelligence`
- List signals: `GET /api/v1/company-signals`
- Company-specific signals: `GET /api/v1/companies/{company_id}/signals`

## 9) Recommendation / decision engine behavior (high level)
- Refresh endpoint: `POST /api/v1/recommendations/refresh`
- List/filter endpoint: `GET /api/v1/recommendations?status=open&urgency=high`
- Detail endpoint: `GET /api/v1/recommendations/{id}`

Decision inputs are deterministic:
- opportunity score
- opportunity signals (severity + recency)
- company intelligence signals
- network node quality
- staleness/timing

Output categories:
- `OPPORTUNITY_PRIORITY`
- `SIGNAL_ALERT`
- `NETWORK_ACTION`
- `FOLLOW_UP_ACTION`
- `WATCHLIST_ESCALATION`

Closed/archived/rejected opportunities are excluded from active recommendation generation.

## 10) Where to inspect logs and job runs
- Runtime logs:
```bash
make logs
```
- Job runs API:
  - `GET /api/v1/admin/jobs/runs`
- Admin UI:
  - `/admin`

## 11) Basic troubleshooting
- API unavailable from frontend:
  - verify `NEXT_PUBLIC_API_URL`
  - verify backend is reachable at `http://localhost:8000`
- DB connection failures:
  - check `DATABASE_URL`
  - ensure Postgres is running and migration head is applied
- No recommendations shown:
  - trigger `POST /api/v1/recommendations/refresh`
  - check `GET /api/v1/recommendations?status=open`
- No realtime updates:
  - check `GET /api/v1/events/stream` and browser network tab

## 12) Known MVP limitations
- Auth/multi-user tenancy is not implemented.
- Connectors are intentionally minimal (MVP mock + RSS parsing path).
- Strategy path is deterministic by default.
- UI is functional and compact, not fully polished.
