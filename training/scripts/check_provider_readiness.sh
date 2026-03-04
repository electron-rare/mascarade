#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "[ERROR] .env not found"
  exit 1
fi

set -a
source .env
set +a

check_var() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    echo "[OK] $name set"
  else
    echo "[WARN] $name missing"
  fi
}

echo "[INFO] Provider credential readiness"
check_var AWS_ACCESS_KEY_ID
check_var AWS_SECRET_ACCESS_KEY
check_var AWS_REGION
check_var AWS_BEDROCK_MODEL_ID
check_var OPENAI_API_KEY
check_var ANTHROPIC_API_KEY
check_var GOOGLE_API_KEY
check_var MISTRAL_API_KEY
check_var HUGGINGFACE_API_KEY

if [[ -n "${HUGGINGFACE_BASE_URL:-}" ]]; then
  echo "[OK] HUGGINGFACE_BASE_URL set"
else
  echo "[INFO] HUGGINGFACE_BASE_URL unset (default: https://router.huggingface.co/v1)"
fi

if [[ -n "${HUGGINGFACE_MODEL:-}" ]]; then
  echo "[OK] HUGGINGFACE_MODEL set"
else
  echo "[INFO] HUGGINGFACE_MODEL unset (default in app config)"
fi

echo "[INFO] API health"
if ! curl -fsS http://127.0.0.1:3100/health >/tmp/mascarade_health.json 2>/tmp/mascarade_health.err; then
  echo "[ERROR] API not reachable on http://127.0.0.1:3100"
  cat /tmp/mascarade_health.err
  exit 1
fi
cat /tmp/mascarade_health.json

echo
echo "[INFO] Providers enabled in core (via /health.core.providers)"
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/mascarade_health.json").read_text(encoding="utf-8"))
core = payload.get("core", {})
providers = core.get("providers", [])
print(providers)
if not providers:
    print("[WARN] no provider enabled in core")
PY
