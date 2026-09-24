#!/bin/sh
set -eu

# .env uses DB_*; the official Postgres image reads POSTGRES_* and PGPORT.
export POSTGRES_USER="${DB_USER:-${POSTGRES_USER:-postgres}}"
export POSTGRES_PASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD:-postgres}}"
export POSTGRES_DB="${DB_NAME:-${POSTGRES_DB:-build_phase_p029}}"
export PGPORT="${DB_PORT:-${PGPORT:-5432}}"

exec docker-entrypoint.sh "$@"
