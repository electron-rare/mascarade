#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_URL="http://127.0.0.1:8100"
DOMAIN="kicad"
MODEL="mistral-large-latest"
MAX_SOURCE_SAMPLES="1"
SAMPLES_PER_SOURCE="1"
CONCURRENCY="1"
JSON_RETRIES="2"
SKIP_CACHE_RESET=0

usage() {
  cat <<'EOF'
Usage: debug_mistral_smoke.sh [options]

Options:
  --api-url URL              Core API URL (default: http://127.0.0.1:8100)
  --domain NAME             Domain to distill (default: kicad)
  --model NAME              Teacher model (default: mistral-large-latest)
  --max-source-samples N    Number of source rows (default: 1)
  --samples-per-source N    Number of distilled rows per source (default: 1)
  --concurrency N           Parallel teacher calls (default: 1)
  --json-retries N          JSON repair retries (default: 2)
  --skip-cache-reset        Do not call /cache/reset and /metrics/reset
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --api-url)
      API_URL="${2:?missing api url}"
      shift 2
      ;;
    --domain)
      DOMAIN="${2:?missing domain}"
      shift 2
      ;;
    --model)
      MODEL="${2:?missing model}"
      shift 2
      ;;
    --max-source-samples)
      MAX_SOURCE_SAMPLES="${2:?missing value}"
      shift 2
      ;;
    --samples-per-source)
      SAMPLES_PER_SOURCE="${2:?missing value}"
      shift 2
      ;;
    --concurrency)
      CONCURRENCY="${2:?missing value}"
      shift 2
      ;;
    --json-retries)
      JSON_RETRIES="${2:?missing value}"
      shift 2
      ;;
    --skip-cache-reset)
      SKIP_CACHE_RESET=1
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
source "$ROOT_DIR/venv_tuning/bin/activate"

if [ "$SKIP_CACHE_RESET" -eq 0 ]; then
  echo "[INFO] resetting cache and metrics on $API_URL"
  curl -fsS -X POST "$API_URL/cache/reset" >/dev/null
  curl -fsS -X POST "$API_URL/metrics/reset" >/dev/null
fi

echo "[INFO] providers: $(curl -fsS "$API_URL/providers")"

python "$ROOT_DIR/finetune/distill_dataset.py" "$DOMAIN" \
  --api-url "$API_URL" \
  --teacher-provider mistral \
  --teacher-model "$MODEL" \
  --max-source-samples "$MAX_SOURCE_SAMPLES" \
  --samples-per-source "$SAMPLES_PER_SOURCE" \
  --concurrency "$CONCURRENCY" \
  --json-retries "$JSON_RETRIES" \
  --verbose
