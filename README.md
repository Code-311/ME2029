# Career Radar (Locked MVP)

Career Radar is a compact career-intelligence MVP that ingests opportunities, scores them, derives signals, and produces deterministic action recommendations.

## Architecture (high level)
- **Backend:** FastAPI + SQLAlchemy + Alembic + APScheduler
- **Frontend:** Next.js + TypeScript
- **Database:** PostgreSQL
- **Realtime:** SSE (`/api/v1/events/stream`)
- **Data flows:**
  - Opportunity ingest/connectors/CSV
  - Scoring engine
  - Opportunity signals + company intelligence signals
  - Deterministic decision engine recommendations
  - Scheduler + admin-triggered jobs

## Quick start
```bash
cp .env.example .env 2>/dev/null || true
make up
```

Then open:
- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs

Useful commands:
```bash
make migrate
make test-backend
make test-frontend
make logs
make down
```

## Operations guide
See **[HOWTO.md](./HOWTO.md)** for full local operation details, scheduler cadence, connector/recommendation behavior, troubleshooting, and current MVP limitations.

## CI
GitHub Actions runs backend and frontend validation on push and pull request.

## MVP scope lock
This repo is intentionally locked to a compact MVP. New major capabilities should be captured as future work, not added in this stabilization pass.
