# Log Monitor

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
Compose. AWS deploy hasn't happened yet.

- `POST /logs` — requires an `X-API-Key` header; enqueues a log event onto Redis/RQ; returns `202` (no `id` — the worker persists it asynchronously)
- `GET /logs` — query with filters (`service`, `level`, `start`, `end`, `limit`, `offset`); open, so the browser dashboard needs no secret
- `worker` service — persists events to Postgres, tracks a rolling per-service error rate, and alerts (stdout + optional webhook) when it crosses threshold
- Dashboard — live filtered feed, stacked-by-severity events-over-time chart, stat tiles
- SQLAlchemy schema + Alembic migration for `log_events`
- Docker Compose for `api` + `worker` + `frontend` + `db` + `redis`

## Quickstart

```bash
cp .env.example .env
# put a real key in .env:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up --build
```

`.env` (next to `docker-compose.yml`) is gitignored. Compose substitutes
`API_KEY` from it into the `api` container. If it's missing or empty, every
`POST /logs` is rejected with `401`.

Then, with the same key exported in your shell (`export API_KEY=...`):

```bash
# Ingest (202 — the worker persists it asynchronously)
curl -X POST http://localhost:8000/logs \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"service":"auth-api","level":"ERROR","message":"boom","timestamp":"2026-04-25T12:00:00Z"}'

# Query (give the worker a moment to catch up)
curl 'http://localhost:8000/logs?service=auth-api&level=ERROR&limit=10'
```

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:5173

## Demo

A full walkthrough that shows ingestion, the dashboard, auth, and an alert.
It runs against the local stack and takes about five minutes.

### 1. Start from a clean slate

```bash
docker compose down -v          # drops old data and alert cooldowns
docker compose up --build
```

Wait until `http://localhost:8000/ready` returns `{"status":"ready"}`, then
open the dashboard at http://localhost:5173 next to a terminal.

### 2. Seed baseline traffic

Healthy traffic across three services with a few errors, so the chart has
history and no alert fires yet:

```bash
export API_KEY=<the key from .env>

send() { curl -s -o /dev/null -X POST http://localhost:8000/logs \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d "{\"service\":\"$1\",\"level\":\"$2\",\"message\":\"$3\"}"; }

for i in $(seq 1 60); do
  send auth-api INFO "login ok"
  send checkout WARNING "slow upstream response"
  send search INFO "query served"
  [ $((i % 10)) -eq 0 ] && send search ERROR "timeout talking to index"
  sleep 0.5
done
```

Events are stamped with the current time when `timestamp` is omitted, so
they land inside the dashboard's recent time ranges.

### 3. Walk through the dashboard

Show the stat tiles, the events-over-time chart (stacked by severity), and
the live table. Filter by service and by level.

### 4. Ingest one event and show the async contract

```bash
curl -i -X POST http://localhost:8000/logs \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"service":"auth-api","level":"INFO","message":"demo event"}'
```

The response is `202` with no `id`: the worker persists the event
afterwards, so it appears in the table a moment later.

### 5. Show the API key check

```bash
curl -i -X POST http://localhost:8000/logs \
  -H 'Content-Type: application/json' \
  -d '{"service":"auth-api","level":"INFO","message":"no key"}'
```

Returns `401`. `GET /logs` stays open on purpose, since the browser
dashboard can't hold a secret.

### 6. Trigger an anomaly alert

Eight errors for one service push its error rate over the default 50%
threshold (with at least 5 events in the 5-minute window):

```bash
for i in 1 2 3 4 5 6 7 8; do send payments ERROR "card processor down $i"; done
docker compose logs worker | grep ALERT
```

You should see an `[ALERT] payments: error rate ...` line. Repeating the
burst won't alert again for five minutes (the cooldown). To re-run the
alert straight away:

```bash
docker compose exec redis redis-cli DEL alert_cooldown:payments
```

To also see a webhook delivery, add `ALERT_WEBHOOK_URL` under the `worker`
service's `environment` in `docker-compose.yml` (it is only passed through
in `docker-compose.prod.yml` by default), point it at a throwaway receiver
such as https://webhook.site, and restart the worker.

### 7. Show the API docs

Open http://localhost:8000/docs for the interactive OpenAPI UI.

## Tests

```bash
cd backend && uv run pytest -q             # backend (dev deps aren't in the image)
cd frontend && npm run test                 # frontend
```

## Layout

```
backend/    FastAPI app, worker, models, migrations, tests
frontend/   Vite + React dashboard
docker-compose.yml
```
