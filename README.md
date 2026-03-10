# Career Intelligence Agent + Career Radar Dashboard (MVP+)

## Architecture
- **Backend**: FastAPI + SQLAlchemy + Alembic + APScheduler (`/backend`)
- **Frontend**: Next.js + TypeScript + Tailwind (`/frontend`)
- **DB**: PostgreSQL via Docker Compose
- **Realtime**: SSE (`/api/v1/events/stream`) with event ids + heartbeat + frontend reconnect state.
- **Adapters**: Connectors normalize external rows into a canonical payload before shared ingestion/upsert/scoring/signals.

## Core capabilities
- Structured profile engine with seeded senior ops/governance/security persona.
- Opportunity ingest (manual, CSV, connectors), CRUD, status updates.
- Explainable scoring engine with weighted factors and per-factor breakdown.
- Signal layer for opportunities/companies.
- Network intelligence + top entry-point recommendations.
- Weekly micro-actions + monthly strategy reviews.
- Background automation (ingest/rescore/strategy/stale checks).
- Job observability via persisted `job_runs` history and admin UI.

## Connector architecture
Flow:
`connector.fetch -> normalize -> ingestion upsert -> scoring -> signals -> SSE bump`

Implemented connectors:
- `csv`: robust CSV header normalization.
- `recruiter_leads`: ingests recruiter lead CSV rows and creates recruiter person nodes.
- `company_careers`: Greenhouse board API adapter (`company` + `board_token`).
- `rss_feed`: RSS ingestion (`feed_url`) via item parsing.
- existing mock connectors remain available for offline dev.

Idempotency:
- opportunities include `ingestion_key` + `external_id`.
- upserts are keyed by `ingestion_key` to avoid duplicates on repeated runs.

## Admin connector controls
- `GET /api/v1/admin/connectors` list available connectors.
- `POST /api/v1/admin/connectors/{name}/run` run one connector manually.
- `/admin` UI includes connector run buttons and job run history.

## Scheduler behavior
APScheduler starts on backend startup and runs:
## What this build improves
This iteration adds real external connector ingestion while preserving the existing FastAPI/Next/Postgres/scoring/signals/scheduler/SSE architecture.

## Connector architecture
All connectors now follow one shared flow:

`connector fetch -> normalize (canonical payload) -> ingestion upsert -> score -> signals -> SSE bump`

Implementation details:
- Shared connector contract in `backend/app/services/connectors.py`.
- Canonical normalized payload (`NormalizedOpportunityInput`) used by every connector.
- Connector registry supports discovery + run-by-name.
- Ingestion service enforces idempotent upsert via:
  - `(source, external_id)` where available,
  - `source_url` fallback,
  - stable ingestion hash key fallback.
- Connectors do not write DB tables directly.

## Supported connectors
- **CSV connector**
  - robust header aliases (`organization/title/salary/job_url/id`, etc)
  - safe numeric parsing for compensation
  - supports external IDs for dedupe
- **Recruiter leads connector**
  - ingests structured recruiter lead CSV
  - creates/updates recruiter network nodes (`PersonNode`)
  - emits recruiter signals (`new_recruiter_contact`, `recruiter_lead_added`)
  - optionally links recruiter-led opportunities through external IDs
- **Company careers connector**
  - configurable company list and careers URLs
  - currently includes a real site-aware adapter for **Lever JSON** endpoints
  - repeat runs are idempotent via external_id/source_url/ingest_key
- **RSS connector**
  - ingests configured RSS feeds and normalizes into opportunities

## Scheduler behavior
APScheduler continues to run core jobs and now supports connector jobs safely:
- ingest: every 30m
- rescore: every 20m
- strategy: every 60m
- stale check/signals: every 6h

Each run writes `job_runs` with status, processed count, timestamps, and summary.

## SSE behavior
SSE is used for one-way dashboard refreshes and lower ops complexity than websockets.
- Backend emits `id`, `data`, `retry`, and heartbeat comments.
- Frontend reconnects and tracks connection status.
- connector jobs (non-CSV): every 45m each

Each run persists `job_runs` with counts and summary fields (fetched/created/updated/skipped/errored where available).

## Admin API + UI
New admin APIs:
- `GET /api/v1/admin/connectors`
- `POST /api/v1/admin/connectors/{connector_name}/run`
- `GET /api/v1/admin/connectors/outcomes`

Admin UI (`/admin`) now shows:
- available connectors and run controls
- recent connector outcomes
- existing job run history

## Configuration
Set connector source configuration through env vars:
- `RECRUITER_LEADS_CONFIG` (JSON)
- `COMPANY_CAREERS_CONFIG` (JSON)
- `RSS_FEEDS_CONFIG` (JSON)

See `.env.example` for working examples.

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
On first backend startup, seed inserts sample profile/config/company/network node/opportunity/signals.

## Known limitations
- Company careers connector currently supports Greenhouse boards only; add site-specific adapters for other ATS platforms.
- RSS item parsing is lightweight and feed-dependent.
- Auth/multi-user tenancy not implemented.
## Adding a new connector
1. Implement `BaseConnector.fetch()` in `backend/app/services/connectors.py`.
2. Return `ConnectorPayload` with normalized opportunity data.
3. Register connector class in `ConnectorRegistry`.
4. Optionally add config in settings/env and admin trigger.
5. Add tests for normalization + ingestion behavior.
