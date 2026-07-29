# Notes

Design decisions, caveats, and what's left. See README.md for how to run things.

## Repo layout

```
Log Anomaly Detection/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory, /health, router wiring
│   │   ├── config.py            # pydantic-settings, env-driven config
│   │   ├── db.py                # async SQLAlchemy engine + Base + get_session
│   │   ├── models.py            # LogEvent ORM model
│   │   ├── schemas.py           # LogEventIn / LogEventAccepted / LogEventOut / LogEventPage
│   │   ├── queue.py             # Redis connection + RQ Queue getter (shared by api + worker)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── logs.py          # POST /logs (enqueues), GET /logs (reads Postgres)
│   │   └── worker/
│   │       ├── __init__.py
│   │       ├── tasks.py         # RQ job: persist event, update rate window, maybe alert
│   │       ├── rate_limiter.py  # ErrorRateTracker — Redis sorted-set rolling window + alert cooldown
│   │       └── alerts.py        # stdout + optional webhook POST
│   ├── alembic/
│   │   ├── env.py               # async migration runner
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_create_log_events.py
│   ├── alembic.ini
│   ├── tests/
│   │   ├── conftest.py               # shared sqlite engine fixture, get_session/get_queue overrides
│   │   ├── test_logs.py              # ingest (202+enqueue), validation, filtering, pagination, health
│   │   ├── test_rate_limiter.py      # ErrorRateTracker unit tests (fakeredis)
│   │   ├── test_worker.py            # worker job unit tests: persistence, alert threshold, cooldown
│   │   └── test_worker_integration.py# real Redis+Postgres+live-worker test; self-skips outside compose
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx / App.tsx / App.css / index.css
│   │   ├── types.ts             # LogEvent / LogEventPage / LogFilters, mirrors backend schemas
│   │   ├── api.ts                # fetchLogs() — GET /logs with filters
│   │   ├── levelStyle.ts         # LogLevel -> color
│   │   ├── bucketEvents.ts       # time-buckets events for the chart
│   │   ├── hooks/useLogs.ts      # polling hook, holds previous data during refetch
│   │   └── components/
│   │       ├── FilterBar.tsx
│   │       ├── StatTiles.tsx
│   │       ├── ErrorRateChart.tsx
│   │       └── LogTable.tsx
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── README.md
└── PROGRESS.md
```

## Design decision: `POST /logs` is async (202, no `id`)

Once the worker owns persistence, `POST /logs` can't synchronously return a
DB `id` anymore. Went with `202 Accepted` and no `id` rather than keeping a
synchronous write *and* enqueueing a copy — that would've made the queue
cosmetic instead of load-bearing. Consequences:

- `POST /logs` echoes back `{status: "queued", service, level, message, timestamp}` — no `id`/`received_at`.
- There's read-after-write lag: a `GET /logs` right after a `POST` may not show the new event yet (usually well under a second locally).
- The dashboard treats this as a real characteristic of the system, not something to paper over.

## Endpoints

| Method | Path      | Notes |
|--------|-----------|-------|
| POST   | `/logs`   | Enqueues the event for the worker to persist. Server fills `timestamp` if absent. `202` with `{status, service, level, message, timestamp}` — no `id` (see above). |
| GET    | `/logs`   | Filters: `service`, `level`, `start`, `end`. Pagination: `limit` (1–1000, default 100), `offset`. Returns `{items, total}` newest-first. |
| GET    | `/health` | `{"status": "ok"}` |

OpenAPI/Swagger UI at `/docs`.

## Anomaly detection & alerting

`rate_limiter.py`'s `ErrorRateTracker` keeps two Redis ZSETs per service
(`events:{service}`, `errors:{service}`), scored by processing time rather
than the event's self-reported timestamp, since the window is meant to
track recent arrival rate. Each `record()` call trims anything older than
the window first. A `SET NX EX` key debounces repeat alerts per service.

`alerts.py` prints an `[ALERT]` line to stdout and, if `ALERT_WEBHOOK_URL`
is set, also POSTs a JSON payload — logging rather than raising on delivery
failure so a broken webhook doesn't take down the worker.

Thresholds are all env-configurable: `ERROR_RATE_WINDOW_SECONDS` (300),
`ERROR_RATE_THRESHOLD` (0.5), `ERROR_RATE_MIN_EVENTS` (5),
`ALERT_COOLDOWN_SECONDS` (300), `ALERT_WEBHOOK_URL` (unset by default).

## Tests

15 backend tests: request/response contract and filtering (`test_logs.py`),
the rate tracker in isolation against fakeredis (`test_rate_limiter.py`),
the worker's own logic bypassing RQ for speed (`test_worker.py`), and one
integration test that enqueues onto a real queue and polls for the actual
compose `worker` service to pick it up (`test_worker_integration.py`, skips
itself unless Redis is reachable).

## Known caveats

- **No auth on `/logs`.** Fine for local dev, needs something before this
  goes anywhere public — an API key header is the minimum.
- **No rate limiting / batched ingest.** Single-event POST only.
- **`process_log_event` assumes a forking worker.** It calls `asyncio.run()`
  per job against a module-level async engine, which is safe under the
  default `rq worker` (forks a fresh process per job) but would break under
  something like `SimpleWorker` running more than one job in the same
  process — the second job would hit a connection tied to an already-closed
  event loop.
- **Frontend deps are pinned, not latest.** `vite@latest` currently pulls in
  the experimental rolldown bundler, which doesn't have a working native
  binding for darwin-arm64 yet. Pinned to Vite 5.4 / Vitest 2.1 / jsdom 25 /
  React 18 instead. `npm audit` flags a few things against this pin but they
  all trace back to dev-server-only advisories or unused Vitest UI features,
  nothing reachable from the production build.
- **Chart shows the loaded page, not the full filtered range.** The
  dashboard fetches up to 200 events per poll and charts only that page, not
  every event matching the filters — fine for "what's happening right now,"
  not for charting a large historical range without a dedicated aggregation
  endpoint.
- **No custom date range**, just the five presets. Could add one later if
  it's actually needed.

## What's left

Next up is deploying this somewhere instead of just running it locally:

- RDS Postgres instead of the compose `db` service
- ElastiCache Redis instead of the compose `redis` service
- `api` + `worker` on EC2 (or ECS Fargate if it's worth the extra setup)
- Frontend as a static build on S3 + CloudFront
- An API key on `/logs` before any of this is public
- Secrets via AWS Secrets Manager / SSM

Not going to provision any of this without actually meaning to — writing the
Terraform is one thing, running `apply` against a real AWS account is
another.
