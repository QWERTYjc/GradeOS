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

# 禁用 websockets 的 keepalive ping 以避免并发写入冲突
# websockets 库的内部 ping 与应用层的 send_json 冲突会导致 AssertionError
# --ws wsproto: 使用 wsproto 替代 websockets（没有 keepalive ping 竞态问题）
exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8001}" --ws wsproto
