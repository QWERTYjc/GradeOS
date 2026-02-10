#!/bin/sh
set -e

if [ "${OFFLINE_MODE:-}" = "true" ]; then
  echo "OFFLINE_MODE=true: skipping DB migrations."
elif [ -n "${DATABASE_URL:-}" ] || [ -n "${DB_HOST:-}" ]; then
  echo "DB configured: running Alembic migrations in background (non-blocking)."
  # Do not block app start; Railway healthchecks are time-bounded.
  # Keep a hard timeout to avoid hanging forever on DB networking issues.
  (
    timeout 180s alembic upgrade head \
      && echo "Alembic migrations completed." \
      || echo "WARNING: Alembic migrations failed or timed out (service will still start)."
  ) &
else
  echo "No DB configured: skipping migrations."
fi

echo "Starting API server..."
# --ws wsproto: avoid websockets keepalive ping race with app-level sends.
PORT_TO_USE="${PORT:-${API_PORT:-8001}}"
echo "Listening on port: ${PORT_TO_USE}"
exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT_TO_USE}" --ws wsproto
