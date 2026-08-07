#!/usr/bin/env bash
set -euo pipefail

wait_for() {
  local host="$1" port="$2" label="$3" tries=0
  until python - "$host" "$port" <<'PY' 2>/dev/null
import socket, sys
socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=2).close()
PY
  do
    tries=$((tries + 1))
    if [ "$tries" -gt 60 ]; then
      echo "timed out waiting for ${label}" >&2
      exit 1
    fi
    sleep 1
  done
}

wait_for "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}" "postgres"
wait_for "$(python -c "from urllib.parse import urlparse;print(urlparse('${REDIS_URL:-redis://redis:6379/0}').hostname)")" \
         "$(python -c "from urllib.parse import urlparse;print(urlparse('${REDIS_URL:-redis://redis:6379/0}').port or 6379)")" "redis"

case "${1:-api}" in
  api)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
    ;;
  api-dev)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
    ;;
  worker)
    exec celery -A app.worker.celery_app worker --loglevel="${LOG_LEVEL:-INFO}" --concurrency=2
    ;;
  worker-dev)
    exec celery -A app.worker.celery_app worker --loglevel=DEBUG --concurrency=1
    ;;
  *)
    exec "$@"
    ;;
esac
