#!/usr/bin/env bash
set -euo pipefail

LOKI_URL="http://127.0.0.1:${LOKI_PORT:-3101}"
WINDOW="1h"
SELECTOR='{compose_project="mascarade"}'
TOP="5"
JSON_OUTPUT="false"
VERBOSE="false"

show_help() {
  cat <<'HELP'
Usage: scripts/loki_cardinality_report.sh [options]

Report Loki label cardinality over a recent time window using the /series API.

Options:
  -h, --help            Show this help and exit
      --loki-url <url>  Loki base URL (default: http://127.0.0.1:$LOKI_PORT)
      --window <span>   Time window such as 15m, 1h, 6h, 24h (default: 1h)
      --selector <q>    Loki selector used for /series (default: {compose_project="mascarade"})
      --top <n>         Number of top values to keep per label (default: 5)
      --json            Emit a machine-readable JSON result
      --verbose         Print extra debug details
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
    --loki-url)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--loki-url expects a value"; exit 2; }
      LOKI_URL="$2"
      shift
      ;;
    --window)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--window expects a value"; exit 2; }
      WINDOW="$2"
      shift
      ;;
    --selector)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--selector expects a value"; exit 2; }
      SELECTOR="$2"
      shift
      ;;
    --top)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--top expects a value"; exit 2; }
      TOP="$2"
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
      echo "Use: scripts/loki_cardinality_report.sh --help"
      exit 2
      ;;
  esac
  shift
done

if [[ ! "$TOP" =~ ^[0-9]+$ ]] || [[ "$TOP" -le 0 ]]; then
  err "Invalid --top value: $TOP"
  exit 2
fi

require_cmd curl
require_cmd python3

LOKI_URL="${LOKI_URL%/}"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE"' EXIT

read -r START_NS END_NS < <(python3 - "$WINDOW" <<'PY'
import re
import sys
import time

window = sys.argv[1].strip()
match = re.fullmatch(r"(\d+)([smhd])", window, re.IGNORECASE)
if not match:
    raise SystemExit(2)
amount = int(match.group(1))
unit = match.group(2).lower()
factor = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
end_ns = time.time_ns()
start_ns = end_ns - amount * factor * 1_000_000_000
print(start_ns, end_ns)
PY
) || {
  err "Invalid --window value: ${WINDOW}"
  exit 2
}

dbg "loki=${LOKI_URL} selector=${SELECTOR} window=${WINDOW} start_ns=${START_NS} end_ns=${END_NS}"

if ! curl -fsSG "${LOKI_URL}/loki/api/v1/series" \
    --data-urlencode "match[]=${SELECTOR}" \
    --data-urlencode "start=${START_NS}" \
    --data-urlencode "end=${END_NS}" \
    >"$RESPONSE_FILE"; then
  json_failure "failed to query Loki series API"
  exit 1
fi

if [[ "$JSON_OUTPUT" == "true" ]]; then
  if ! python3 - "$RESPONSE_FILE" "$WINDOW" "$SELECTOR" "$TOP" <<'PY'
import json
import sys
from collections import Counter, defaultdict

path, window, selector, top_n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
payload = json.load(open(path, "r", encoding="utf-8"))
series = payload.get("data", [])

labels_of_interest = [
    "service",
    "compose_service",
    "source",
    "run_id",
    "agent_name",
    "event_type",
    "provider",
    "routing_provider",
    "routing_role",
]

counts = {label: Counter() for label in labels_of_interest}
for row in series:
    if not isinstance(row, dict):
        continue
    for label in labels_of_interest:
        value = row.get(label)
        if value:
            counts[label][value] += 1

summary = {}
for label, counter in counts.items():
    summary[label] = {
        "distinct": len(counter),
        "top": counter.most_common(top_n),
    }

print(json.dumps({
    "ok": True,
    "window": window,
    "selector": selector,
    "series_count": len(series),
    "labels": summary,
}, ensure_ascii=True))
PY
  then
    json_failure "invalid Loki JSON response"
    exit 1
  fi
else
  if ! python3 - "$RESPONSE_FILE" "$WINDOW" "$SELECTOR" "$TOP" <<'PY'
import json
import sys
from collections import Counter

path, window, selector, top_n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
payload = json.load(open(path, "r", encoding="utf-8"))
series = payload.get("data", [])

labels_of_interest = [
    "service",
    "compose_service",
    "source",
    "run_id",
    "agent_name",
    "event_type",
    "provider",
    "routing_provider",
    "routing_role",
]

counts = {label: Counter() for label in labels_of_interest}
for row in series:
    if not isinstance(row, dict):
        continue
    for label in labels_of_interest:
        value = row.get(label)
        if value:
            counts[label][value] += 1

print(f"Loki cardinality report ({window})")
print(f"selector: {selector}")
print(f"series: {len(series)}")
for label in labels_of_interest:
    counter = counts[label]
    print(f"- {label}: {len(counter)} distinct")
    for value, score in counter.most_common(top_n):
        print(f"    {value}: {score}")
PY
  then
    json_failure "invalid Loki JSON response"
    exit 1
  fi
fi
