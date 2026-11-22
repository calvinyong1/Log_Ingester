# Backup and restore

`pg_dump` exports a Postgres database to a file; `pg_restore` loads it back.
The retention prune deletes rows permanently, and the only copy of the data is
the `pgdata` Docker volume (which `docker compose down -v` wipes), so take a
dump before changing retention settings or anything destructive.

## Back up

```bash
scripts/backup.sh                  # writes backups/logs-<UTC timestamp>.dump
scripts/backup.sh /path/to/my.dump # or choose the file
```

It runs `pg_dump -Fc` (custom format: compressed, selective restore possible)
inside the `db` container and writes the result on the host. `backups/` is
gitignored. The stack can keep running during a backup; the dump is a
consistent snapshot.

## Restore

```bash
scripts/restore.sh backups/logs-20261122T120000Z.dump
docker compose start api worker
```

The script stops `api` and `worker` first (open connections would stop
`pg_restore --clean` dropping the tables), then replaces the contents of the
`logs` database. The dump includes `alembic_version`, so the schema comes back
at the revision it was dumped at and the `migrate` service has nothing to do.

To restore into a fresh stack (after `docker compose down -v`), bring up the
database first, then restore:

```bash
docker compose up -d db
scripts/restore.sh backups/<file>.dump
docker compose up -d
```

## Caveats

- Prometheus and Grafana keep their own data (`promdata`, `grafanadata`
  volumes); only Postgres is covered here. Redis holds the queue and the
  rolling window, which rebuild themselves.
- Restored rows older than `RETENTION_DAYS` are pruned again on the worker's
  next run (within `PRUNE_INTERVAL_SECONDS`). Raise `RETENTION_DAYS` first to
  keep them.
- Backups are manual; nothing schedules them.

## Verification

Round trip on the dev stack: record the row count, back up, delete every row,
restore, compare.

Run on 2026-11-22 against the dev stack (`docker compose`, Postgres 16):

| Step | `log_events` | `alerts` |
|---|---|---|
| before | 1233 | 3 |
| after `delete from log_events; delete from alerts;` | 0 | 0 |
| after `scripts/restore.sh` | 1233 | 3 |

`alembic_version` was `0004` after the restore, and the API and worker started
cleanly with `docker compose start api worker`.
