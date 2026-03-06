#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="8100"
LOG_FILE="/tmp/mascarade_core_8100.log"
RESTART=0

usage() {
  cat <<'EOF'
Usage: debug_core_8100.sh [--port PORT] [--log-file PATH] [--restart]

Start the Mascarade core with the project .env and tee logs to a file.
By default it runs on 127.0.0.1:8100 and writes logs to /tmp/mascarade_core_8100.log.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --port)
      PORT="${2:?missing port}"
      shift 2
      ;;
    --log-file)
      LOG_FILE="${2:?missing log file}"
      shift 2
      ;;
    --restart)
      RESTART=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

kill_port_listeners() {
  local port="$1"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k -TERM "${port}/tcp" 2>/dev/null || true
  fi

  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  fi

  if [ -z "$pids" ] && command -v ss >/dev/null 2>&1; then
    pids="$(
      ss -lntp "sport = :${port}" 2>/dev/null \
        | awk -F 'pid=' 'NR > 1 && NF > 1 {split($2, a, /[),]/); print a[1]}' \
        | sort -u
    )"
  fi

  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
  fi

  for _ in $(seq 1 20); do
    if ! ss -ltn "sport = :${port}" 2>/dev/null | tail -n +2 | grep -q .; then
      return 0
    fi
    sleep 0.25
  done

  echo "[WARN] port ${port} still busy after restart attempt" >&2
}

if [ "$RESTART" -eq 1 ]; then
  pkill -f "mascarade.server:app --host 127.0.0.1 --port ${PORT}" || true
  kill_port_listeners "$PORT"
fi

mkdir -p "$(dirname "$LOG_FILE")"

source "$ROOT_DIR/core/.venv/bin/activate"
set -a
source "$ROOT_DIR/.env"
set +a

echo "[INFO] root=$ROOT_DIR"
echo "[INFO] port=$PORT"
echo "[INFO] log=$LOG_FILE"

PYTHONPATH="$ROOT_DIR/core" python -m uvicorn mascarade.server:app --host 127.0.0.1 --port "$PORT" 2>&1 | tee "$LOG_FILE"
