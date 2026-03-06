#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://localhost:${GENERATE_AUDIO_PORT:-9000}"
PROMPT="short synthetic click"
DURATION="1.0"
TIMEOUT="180"

show_help() {
  cat <<'HELP'
Usage: scripts/smoke_generate_audio.sh [options]

Run a real HTTP smoke test against the local generate-audio service.

Options:
  -h, --help           Show this help and exit
      --url <url>      Base URL of the service (default: http://localhost:$GENERATE_AUDIO_PORT)
      --prompt <text>  Prompt to generate
      --duration <s>   Requested duration in seconds (default: 1.0)
      --timeout <s>    curl timeout for POST /generate (default: 180)
HELP
}

err() {
  printf 'ERROR: %s\n' "$*" >&2
}

info() {
  printf '%s\n' "$*"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    err "Missing required command: $cmd"
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    --url)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--url expects a value"; exit 2; }
      BASE_URL="$2"
      shift
      ;;
    --prompt)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--prompt expects a value"; exit 2; }
      PROMPT="$2"
      shift
      ;;
    --duration)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--duration expects a value"; exit 2; }
      DURATION="$2"
      shift
      ;;
    --timeout)
      [[ $# -ge 2 && -n "${2:-}" ]] || { err "--timeout expects a value"; exit 2; }
      TIMEOUT="$2"
      shift
      ;;
    *)
      err "Unknown option: $1"
      echo "Use: scripts/smoke_generate_audio.sh --help"
      exit 2
      ;;
  esac
  shift
done

if [[ ! "$DURATION" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  err "Invalid duration: $DURATION"
  exit 2
fi

if [[ ! "$TIMEOUT" =~ ^[0-9]+$ ]]; then
  err "Invalid timeout: $TIMEOUT"
  exit 2
fi

require_cmd curl
require_cmd python3

BASE_URL="${BASE_URL%/}"
BODY_FILE="$(mktemp)"
HEADERS_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE" "$HEADERS_FILE"' EXIT

info "Health check: ${BASE_URL}/health"
HEALTH_JSON="$(curl -fsS --max-time 15 "${BASE_URL}/health")"

mapfile -t HEALTH_FIELDS < <(
  printf '%s' "$HEALTH_JSON" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
fields = [
    "true" if data.get("runtime_ready") else "false",
    data.get("runtime_error") or "",
    "true" if data.get("model_loaded") else "false",
    data.get("torch_variant") or "",
]
print("\n".join(fields))
'
)

RUNTIME_READY="${HEALTH_FIELDS[0]:-false}"
RUNTIME_ERROR="${HEALTH_FIELDS[1]:-}"
MODEL_LOADED="${HEALTH_FIELDS[2]:-false}"
TORCH_VARIANT="${HEALTH_FIELDS[3]:-unknown}"

info "Runtime ready: ${RUNTIME_READY}"
info "Torch variant: ${TORCH_VARIANT}"
info "Model loaded: ${MODEL_LOADED}"

if [[ "$RUNTIME_READY" != "true" ]]; then
  err "generate-audio runtime is not ready: ${RUNTIME_ERROR:-unknown error}"
  exit 1
fi

PAYLOAD="$(python3 - "$PROMPT" "$DURATION" <<'PY'
import json
import sys

prompt = sys.argv[1]
duration = float(sys.argv[2])
print(json.dumps({"prompt": prompt, "duration": duration}))
PY
)"

info "POST ${BASE_URL}/generate"
HTTP_CODE="$(
  curl -sS --show-error \
    --max-time "$TIMEOUT" \
    -o "$BODY_FILE" \
    -D "$HEADERS_FILE" \
    -H "Content-Type: application/json" \
    -X POST "${BASE_URL}/generate" \
    --data "$PAYLOAD" \
    -w "%{http_code}"
)"

if [[ "$HTTP_CODE" != "200" ]]; then
  err "Unexpected HTTP status: $HTTP_CODE"
  if [[ -s "$BODY_FILE" ]]; then
    printf 'Response body:\n' >&2
    cat "$BODY_FILE" >&2
    printf '\n' >&2
  fi
  exit 1
fi

CONTENT_TYPE="$(awk 'BEGIN{IGNORECASE=1} /^Content-Type:/ {print $2; exit}' "$HEADERS_FILE" | tr -d '\r')"
ENGINE_HEADER="$(awk 'BEGIN{IGNORECASE=1} /^X-Audio-Engine:/ {print $2; exit}' "$HEADERS_FILE" | tr -d '\r')"
MODEL_HEADER="$(awk 'BEGIN{IGNORECASE=1} /^X-Audio-Model:/ {$1=""; sub(/^ /, ""); print; exit}' "$HEADERS_FILE" | tr -d '\r')"
DEVICE_HEADER="$(awk 'BEGIN{IGNORECASE=1} /^X-Audio-Device:/ {print $2; exit}' "$HEADERS_FILE" | tr -d '\r')"
BODY_SIZE="$(wc -c < "$BODY_FILE" | tr -d ' ')"

if [[ "$CONTENT_TYPE" != "audio/wav" ]]; then
  err "Unexpected Content-Type: ${CONTENT_TYPE:-missing}"
  exit 1
fi

if [[ -z "$ENGINE_HEADER" || -z "$MODEL_HEADER" || -z "$DEVICE_HEADER" ]]; then
  err "Missing audio metadata headers in response"
  exit 1
fi

if [[ "$BODY_SIZE" -le 0 ]]; then
  err "Received an empty audio response"
  exit 1
fi

info "Smoke test OK"
info "Engine: $ENGINE_HEADER"
info "Model: $MODEL_HEADER"
info "Device: $DEVICE_HEADER"
info "Bytes: $BODY_SIZE"
