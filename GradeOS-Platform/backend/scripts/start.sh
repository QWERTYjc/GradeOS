#!/bin/sh
set -e

if [ "${OFFLINE_MODE:-}" = "true" ]; then
  echo "Skipping migrations (OFFLINE_MODE=true)."
elif [ -n "${DATABASE_URL:-}" ] || [ -n "${DB_HOST:-}" ]; then
  echo "Running database migrations."
  alembic upgrade head
else
  echo "Skipping migrations (no database configured)."
fi

exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8001}"
