#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8100}"
MODEL="${MODEL:-${ANE_MODEL:-}}"
MESSAGE="Respond with exactly: openai compat ok"
API_KEY="${MASCARADE_API_KEY:-}"
TIMEOUT="${TIMEOUT:-}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/smoke_openai_compat_ane.sh [options]

Options:
  --url URL        Core base URL (default: http://127.0.0.1:8100)
  --model MODEL    Explicit model in provider:model format
  --message TEXT   Prompt to send
  --api-key KEY    Bearer token if auth is enabled
  --timeout SEC    Request timeout in seconds (default: 600 for apple-coreml, 120 otherwise)
  -h, --help       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --message)
      MESSAGE="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${MODEL}" ]]; then
  echo "Explicit model required. Pass --model provider:model or export ANE_MODEL." >&2
  exit 2
fi

if [[ -z "${TIMEOUT}" ]]; then
  if [[ "${MODEL}" == apple-coreml:* ]]; then
    TIMEOUT="600"
  else
    TIMEOUT="120"
  fi
fi

if [[ "${BASE_URL}" == */v1/chat/completions ]]; then
  BASE_URL="${BASE_URL%/v1/chat/completions}"
elif [[ "${BASE_URL}" == */v1 ]]; then
  BASE_URL="${BASE_URL%/v1}"
fi

auth_args=()
if [[ -n "${API_KEY}" ]]; then
  auth_args=(-H "Authorization: Bearer ${API_KEY}")
fi

echo "# health"
curl -fsS --max-time "${TIMEOUT}" "${BASE_URL}/health"
echo

echo "# chat completions"
response="$(
  curl -fsS --max-time "${TIMEOUT}" "${BASE_URL}/v1/chat/completions" \
    "${auth_args[@]}" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"${MODEL}\",
      \"messages\": [{\"role\": \"user\", \"content\": \"${MESSAGE}\"}],
      \"temperature\": 0,
      \"max_tokens\": 16
    }"
)"
export MASCARADE_SMOKE_RESPONSE="${response}"
python3 - <<'PY'
from __future__ import annotations

import json
import os

payload = json.loads(os.environ["MASCARADE_SMOKE_RESPONSE"])
print(json.dumps(
    {
        "model": payload.get("model"),
        "content": payload["choices"][0]["message"]["content"],
        "usage": payload.get("usage", {}),
    },
    ensure_ascii=False,
    indent=2,
))
PY
