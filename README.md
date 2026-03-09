# Career Intelligence Agent + Career Radar Dashboard (MVP+)

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

## Adding a new connector
1. Implement `BaseConnector.fetch()` in `backend/app/services/connectors.py`.
2. Return `ConnectorPayload` with normalized opportunity data.
3. Register connector class in `ConnectorRegistry`.
4. Optionally add config in settings/env and admin trigger.
5. Add tests for normalization + ingestion behavior.
