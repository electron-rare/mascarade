#!/usr/bin/env bash
# Start stack pieces, pull recommended Ollama models, and run multi-agent multi-LLM smoke test.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://localhost:3100/api}"
MODE="${MODE:-pipeline}"
PROMPT="${PROMPT:-Construis un plan d implementation robuste pour une stack multi-agents multi-LLM locale.}"
KEY="${KEY:-}"

MODELS=(
  "qwen2.5:3b"
  "qwen2.5-coder:3b"
  "gemma2:2b"
  "phi3:mini"
  "mistral:7b"
)

usage() {
  cat <<'EOF'
Usage: bootstrap-multi-llm.sh [options]

Options:
  --api-url <url>     API URL (default: http://localhost:3100/api)
  --key <token>       API bearer token (optional if auth disabled)
  --mode <mode>       sequential|parallel|pipeline (default: pipeline)
  --prompt <text>     Orchestration prompt
  -h, --help          Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url) API_URL="$2"; shift ;;
    --key) KEY="$2"; shift ;;
    --mode) MODE="$2"; shift ;;
    --prompt) PROMPT="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

echo "[1/5] Starting containers: core, api, ollama"
docker compose up -d core api ollama

echo "[2/5] Waiting for API health"
for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:3100/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "http://localhost:3100/health" >/dev/null

echo "[3/5] Pulling recommended Ollama model pack"
for model in "${MODELS[@]}"; do
  echo "  -> $model"
  docker compose exec -T ollama ollama pull "$model"
done

echo "[4/5] Listing installed models"
docker compose exec -T ollama ollama list

echo "[5/5] Creating multi-agent multi-LLM team + orchestrating"
"$ROOT_DIR/scripts/multi-agent-multi-llm.sh" \
  --api-url "$API_URL" \
  --mode "$MODE" \
  --prompt "$PROMPT" \
  --prefix "team-ml" \
  ${KEY:+--key "$KEY"}
