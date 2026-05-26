#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for database at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."

# Wait for Postgres to be ready using pg_isready
RETRY=0
until pg_isready -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-rdc}" >/dev/null 2>&1; do
  RETRY=$((RETRY+1))
  if [ $RETRY -gt 60 ]; then
    echo "Timed out waiting for Postgres" >&2
    exit 1
  fi
  sleep 1
done

echo "Postgres is ready — running migrations and collecting static files"
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "Starting command: $@"
exec "$@"
