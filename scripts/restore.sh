#!/usr/bin/env bash
# Replace the contents of the logs database with a dump made by scripts/backup.sh.
# Usage: scripts/restore.sh <dumpfile>
set -euo pipefail
cd "$(dirname "$0")/.."

file="${1:?usage: scripts/restore.sh <dumpfile>}"
[ -f "$file" ] || { echo "no such file: $file" >&2; exit 1; }

# Open connections would block --clean from dropping the tables.
docker compose stop api worker
docker compose exec -T db pg_restore -U postgres -d logs --clean --if-exists --no-owner < "$file"
echo "Restored $file. Start the services again: docker compose start api worker"
