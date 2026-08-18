#!/usr/bin/env bash
set -euo pipefail

APP_UID=10001
APP_GID=10001
STORAGE_ROOT="${STORAGE_ROOT:-/var/lib/finmanager/storage}"

# Every attachment the app ever writes lands under one volume that is mounted by
# containers running as two different users: the runtime image serves requests as
# `finmanager`, while `./fm seed`, `./fm check` and the dev overlay run as root
# against a bind-mounted source tree. Without this, a document written by the
# seed leaves a root-owned shard directory that the API cannot write into, and
# every upload dies with `PermissionError` (ADR-0024).
umask 002

prepare_storage() {
  [ "$(id -u)" = "0" ] || return 0
  mkdir -p "$STORAGE_ROOT"
  chown -R "root:${APP_GID}" "$STORAGE_ROOT"
  chmod -R g+rwX "$STORAGE_ROOT"
  find "$STORAGE_ROOT" -type d -exec chmod g+s {} +
}

# Re-exec as the unprivileged app user. Only the few lines above ever run as
# root; nothing that parses a document or serves a request does.
drop_privileges() {
  [ "$(id -u)" = "0" ] || return 0
  exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --init-groups --inh-caps=-all \
    "$0" "$@"
}

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

prepare_storage
case "${1:-api}" in
  api | worker) drop_privileges "$@" ;;
esac

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
