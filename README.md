# Log Anomaly Detection

Real-time log monitoring service: ingest application logs over HTTP, store them in
Postgres, detect anomalies via a Redis/RQ worker, and visualise the stream in a
React dashboard.

## Stack

- **Backend:** FastAPI, async SQLAlchemy 2.0, Postgres 16, Alembic
- **Queue:** Redis 7 + RQ
- **Frontend:** Vite + React + TypeScript, Recharts
- **Infra:** Docker Compose locally, AWS (EC2 / RDS / ElastiCache) for deploy

## Status

Backend, worker, and dashboard all work end to end locally via Docker
Compose. AWS deploy hasn't happened yet — see `PROGRESS.md`.

- `POST /logs` — enqueues a log event onto Redis/RQ; returns `202` (no `id` — the worker persists it asynchronously)
- `GET /logs` — query with filters (`service`, `level`, `start`, `end`, `limit`, `offset`)
- `worker` service — persists events to Postgres, tracks a rolling per-service error rate, and alerts (stdout + optional webhook) when it crosses threshold
- Dashboard — live filtered feed, stacked-by-severity events-over-time chart, stat tiles
- SQLAlchemy schema + Alembic migration for `log_events`
- Docker Compose for `api` + `worker` + `frontend` + `db` + `redis`

## Quickstart

```bash
docker compose up --build
```

Then:

```bash
# Ingest (202 — the worker persists it asynchronously)
curl -X POST http://localhost:8000/logs \
  -H 'Content-Type: application/json' \
  -d '{"service":"auth-api","level":"ERROR","message":"boom","timestamp":"2026-04-25T12:00:00Z"}'

# Query (give the worker a moment to catch up)
curl 'http://localhost:8000/logs?service=auth-api&level=ERROR&limit=10'
```

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:5173

## Tests

```bash
docker compose exec api uv run pytest -q   # backend
cd frontend && npm run test                 # frontend
```

## Layout

```
backend/    FastAPI app, worker, models, migrations, tests
frontend/   Vite + React dashboard
docker-compose.yml
```

See `PROGRESS.md` for full design notes, caveats, and what's next.
