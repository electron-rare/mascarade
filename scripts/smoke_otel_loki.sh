#!/usr/bin/env bash
set -euo pipefail

COLLECTOR_URL="http://127.0.0.1:${OTEL_COLLECTOR_HTTP_PORT:-4318}"
COLLECTOR_HEALTH_URL="http://127.0.0.1:${OTEL_COLLECTOR_HEALTH_PORT:-13133}/health"
LOKI_URL="http://127.0.0.1:${LOKI_PORT:-3101}"
WAIT_SECONDS="10"
POLL_INTERVAL="1"
SOURCE="otel-smoke"
AGENT_NAME="smoke-agent"
EVENT_TYPE="smoke"
MODE="smoke"
PROVIDER="collector"
ROUTING_ROLE="ops"
ROUTING_PROVIDER="collector"
JSON_OUTPUT="false"
VERBOSE="false"
RUN_ID=""
MESSAGE_PREFIX="otel collector smoke"

show_help() {
  cat <<'HELP'
Usage: scripts/smoke_otel_loki.sh [options]

Run a real OTLP HTTP smoke test against the local collector and verify
that the log becomes queryable in Loki.

Options:
  -h, --help                 Show this help and exit
      --collector-url <url>  Collector base URL (default: http://127.0.0.1:$OTEL_COLLECTOR_HTTP_PORT)
      --health-url <url>     Collector health URL (default: http://127.0.0.1:$OTEL_COLLECTOR_HEALTH_PORT/health)
      --loki-url <url>       Loki base URL (default: http://127.0.0.1:$LOKI_PORT)
      --run-id <id>          Force a specific run_id
      --wait <seconds>       Max wait for Loki ingestion (default: 10)
      --interval <seconds>   Poll interval while waiting for Loki (default: 1)
      --json                 Emit a machine-readable JSON result
      --verbose              Print extra probe details
HELP
}

err() {
  printf 'ERROR: %s\n' "$*" >&2
}

info() {
  [[ "$JSON_OUTPUT" == "true" ]] || printf '%s\n' "$*"
}

dbg() {
  [[ "$VERBOSE" == "true" && "$JSON_OUTPUT" != "true" ]] && printf '[dbg] %s\n' "$*" >&2 || true
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    err "Missing required command: $cmd"
    exit 1
  fi
}

json_failure() {
  local message="$1"
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    python3 - "$message" <<'PY'
import json
import sys

print(json.dumps({"ok": False, "error": sys.argv[1]}, ensure_ascii=True))
PY
  else
    err "$message"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    --collector-url)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--collector-url expects a value"; exit 2; }
      COLLECTOR_URL="$2"
      shift
      ;;
    --health-url)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--health-url expects a value"; exit 2; }
      COLLECTOR_HEALTH_URL="$2"
      shift
      ;;
    --loki-url)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--loki-url expects a value"; exit 2; }
      LOKI_URL="$2"
      shift
      ;;
    --run-id)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--run-id expects a value"; exit 2; }
      RUN_ID="$2"
      shift
      ;;
    --wait)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--wait expects a value"; exit 2; }
      WAIT_SECONDS="$2"
      shift
      ;;
    --interval)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--interval expects a value"; exit 2; }
      POLL_INTERVAL="$2"
      shift
      ;;
    --json)
      JSON_OUTPUT="true"
      ;;
    --verbose)
      VERBOSE="true"
      ;;
    *)
      err "Unknown option: $1"
      echo "Use: scripts/smoke_otel_loki.sh --help"
      exit 2
      ;;
  esac
  shift
done

if [[ ! "$WAIT_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  err "Invalid wait value: $WAIT_SECONDS"
  exit 2
fi

if [[ ! "$POLL_INTERVAL" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  err "Invalid interval value: $POLL_INTERVAL"
  exit 2
fi

require_cmd curl
require_cmd python3

COLLECTOR_URL="${COLLECTOR_URL%/}"
LOKI_URL="${LOKI_URL%/}"
RUN_ID="${RUN_ID:-otel-smoke-$(date +%s)}"
MESSAGE="${MESSAGE_PREFIX} ${RUN_ID}"
START_NS="$(date +%s%N)"
PAYLOAD_FILE="$(mktemp)"
POST_BODY_FILE="$(mktemp)"
QUERY_BODY_FILE="$(mktemp)"
QUERY_ERROR_FILE="$(mktemp)"
trap 'rm -f "$PAYLOAD_FILE" "$POST_BODY_FILE" "$QUERY_BODY_FILE" "$QUERY_ERROR_FILE"' EXIT

dbg "collector=${COLLECTOR_URL} health=${COLLECTOR_HEALTH_URL} loki=${LOKI_URL} run_id=${RUN_ID}"

if ! HEALTH_JSON="$(curl -fsS --max-time 10 "$COLLECTOR_HEALTH_URL")"; then
  json_failure "collector health probe failed: ${COLLECTOR_HEALTH_URL}"
  exit 1
fi

if ! python3 - "$HEALTH_JSON" <<'PY' >/dev/null
import json
import sys

payload = json.loads(sys.argv[1])
status = str(payload.get("status") or "").lower()
if "available" not in status and status not in {"ok", "healthy", "ready"}:
    raise SystemExit(1)
PY
then
  json_failure "collector health payload is not ready"
  exit 1
fi

python3 - "$RUN_ID" "$MESSAGE" "$SOURCE" "$AGENT_NAME" "$EVENT_TYPE" "$MODE" "$PROVIDER" "$ROUTING_ROLE" "$ROUTING_PROVIDER" >"$PAYLOAD_FILE" <<'PY'
import json
import sys
import time

run_id, message, source, agent_name, event_type, mode, provider, routing_role, routing_provider = sys.argv[1:]

payload = {
    "resourceLogs": [
        {
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "otel-smoke"}}
                ]
            },
            "scopeLogs": [
                {
                    "scope": {"name": "smoke_otel_loki"},
                    "logRecords": [
                        {
                            "timeUnixNano": str(time.time_ns()),
                            "severityText": "INFO",
                            "severityNumber": 9,
                            "body": {"stringValue": message},
                            "attributes": [
                                {"key": "source", "value": {"stringValue": source}},
                                {"key": "run_id", "value": {"stringValue": run_id}},
                                {"key": "agent_name", "value": {"stringValue": agent_name}},
                                {"key": "event_type", "value": {"stringValue": event_type}},
                                {"key": "mode", "value": {"stringValue": mode}},
                                {"key": "provider", "value": {"stringValue": provider}},
                                {"key": "routing_role", "value": {"stringValue": routing_role}},
                                {"key": "routing_provider", "value": {"stringValue": routing_provider}},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
}

print(json.dumps(payload, ensure_ascii=True))
PY

POST_HTTP_CODE="$(
  curl -sS --show-error \
    --max-time 10 \
    -o "$POST_BODY_FILE" \
    -H "Content-Type: application/json" \
    -X POST "${COLLECTOR_URL}/v1/logs" \
    --data @"$PAYLOAD_FILE" \
    -w "%{http_code}"
)"

if [[ "$POST_HTTP_CODE" != "200" ]]; then
  RESPONSE_BODY="$(tr -d '\n' < "$POST_BODY_FILE")"
  json_failure "collector rejected OTLP payload: HTTP ${POST_HTTP_CODE}${RESPONSE_BODY:+ / ${RESPONSE_BODY}}"
  exit 1
fi

FOUND_JSON=""
DEADLINE_EPOCH="$(python3 - "$WAIT_SECONDS" <<'PY'
import sys
import time

print(time.time() + float(sys.argv[1]))
PY
)"

while python3 - "$DEADLINE_EPOCH" <<'PY' >/dev/null
import sys
import time

raise SystemExit(0 if time.time() <= float(sys.argv[1]) else 1)
PY
do
  END_NS="$(date +%s%N)"
  if curl -fsSG "${LOKI_URL}/loki/api/v1/query_range" \
      --data-urlencode "query={source=\"${SOURCE}\",run_id=\"${RUN_ID}\"}" \
      --data-urlencode "start=${START_NS}" \
      --data-urlencode "end=${END_NS}" \
      --data-urlencode "limit=5" \
      >"$QUERY_BODY_FILE"; then
    if FOUND_JSON="$(python3 - "$QUERY_BODY_FILE" "$RUN_ID" "$MESSAGE" 2>"$QUERY_ERROR_FILE" <<'PY'
import json
import sys

path, run_id, message = sys.argv[1:]
required = {
    "source",
    "run_id",
    "agent_name",
    "event_type",
    "mode",
    "provider",
    "routing_role",
    "routing_provider",
}

payload = json.load(open(path, "r", encoding="utf-8"))
streams = payload.get("data", {}).get("result", [])
for stream in streams:
    labels = stream.get("stream") or {}
    values = stream.get("values") or []
    if labels.get("run_id") != run_id:
        continue
    missing = sorted(required.difference(labels))
    if missing:
        raise SystemExit(f"missing labels: {', '.join(missing)}")
    for value in values:
        if not isinstance(value, list) or len(value) < 2:
            continue
        line = value[1]
        if message not in line:
            continue
        print(json.dumps({
            "labels": labels,
            "line": line,
            "timestamp_ns": value[0],
        }, ensure_ascii=True))
        raise SystemExit(0)

raise SystemExit(2)
PY
    )"; then
      break
    else
      rc=$?
      if [[ $rc -eq 1 ]]; then
        json_failure "$(tr -d '\n' < "$QUERY_ERROR_FILE")"
        exit 1
      fi
    fi
  fi

  sleep "$POLL_INTERVAL"
done

if [[ -z "$FOUND_JSON" ]]; then
  json_failure "log not observed in Loki before timeout"
  exit 1
fi

if [[ "$JSON_OUTPUT" == "true" ]]; then
  python3 - "$RUN_ID" "$COLLECTOR_URL" "$LOKI_URL" "$FOUND_JSON" <<'PY'
import json
import sys

run_id, collector_url, loki_url, found_json = sys.argv[1:]
found = json.loads(found_json)
print(json.dumps({
    "ok": True,
    "run_id": run_id,
    "collector_url": collector_url,
    "loki_url": loki_url,
    "labels": found["labels"],
    "line": found["line"],
    "timestamp_ns": found["timestamp_ns"],
}, ensure_ascii=True))
PY
else
  info "Smoke test OK"
  info "run_id: ${RUN_ID}"
  info "collector: ${COLLECTOR_URL}"
  info "loki: ${LOKI_URL}"
  info "selector: {source=\"${SOURCE}\",run_id=\"${RUN_ID}\"}"
fi
