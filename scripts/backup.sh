#!/usr/bin/env bash
# Dump the logs database from the compose `db` service to a pg_dump custom-format
# file (compressed, restorable with pg_restore). Usage: scripts/backup.sh [outfile]
set -euo pipefail
cd "$(dirname "$0")/.."

out="${1:-backups/logs-$(date -u +%Y%m%dT%H%M%SZ).dump}"
mkdir -p "$(dirname "$out")"

# Write to a temp name so a failed dump never leaves something that looks like a backup.
docker compose exec -T db pg_dump -U postgres -Fc logs > "$out.partial"
mv "$out.partial" "$out"
echo "Wrote $out ($(wc -c < "$out" | tr -d ' ') bytes)"
