#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://127.0.0.1:${APPLE_LLM_PORT:-8201}"
MODEL="${APPLE_LLM_MODEL_ID:-apple-local}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      BASE_URL="$2"
      shift 2
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--url <url>] [--model <model>]" >&2
      exit 2
      ;;
  esac
done

echo "# health"
curl -fsS "${BASE_URL}/health"
echo
echo "# models"
curl -fsS "${BASE_URL}/models"
echo
echo "# generate"
curl -fsS "${BASE_URL}/generate" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"${MODEL}\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Respond with exactly: apple runtime ok\"}],
    \"temperature\": 0,
    \"max_tokens\": 32
  }"
echo
