#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ] && [ -n "${POSTGRES_HOST:-}" ]; then
  echo "Waiting for local PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."

# Wait for the local Compose database only. Render workers use DATABASE_URL.
RETRY=0
until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-rdc}" >/dev/null 2>&1; do
  RETRY=$((RETRY+1))
  if [ "$RETRY" -gt 60 ]; then
    echo "Timed out waiting for PostgreSQL" >&2
    exit 1
  fi
  sleep 1
done

fi

if [ "${RUN_DJANGO_STARTUP_TASKS:-false}" = "true" ]; then
  echo "Running web-service startup tasks"
fi
if [ "${RUN_DJANGO_STARTUP_TASKS:-false}" = "true" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi

echo "Starting command: $@"
exec "$@"
