#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://localhost:3100}"
EVAL_FILE="${EVAL_FILE:-training/data/eval.sample.jsonl}"
OUT_FILE="${OUT_FILE:-training/output/baseline_results.quick.jsonl}"
SUMMARY_FILE="${SUMMARY_FILE:-training/output/baseline_summary.quick.md}"
DEFAULT_PROVIDERS="bedrock,openai,claude,google,mistral,huggingface"

load_api_key_from_env_file() {
  if [[ -n "${MASCARADE_API_KEY:-}" || ! -f .env ]]; then
    return 0
  fi

  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
}

discover_providers() {
  API_URL="$API_URL" API_KEY="${MASCARADE_API_KEY:-}" python3 - <<'PY'
import json
import os
import urllib.error
import urllib.request


def fetch(url: str, headers: dict[str, str]) -> dict | None:
    req = urllib.request.Request(url, method="GET")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


api_url = os.environ["API_URL"].rstrip("/")
api_key = os.environ.get("API_KEY", "")
providers: list[str] = []

health_payload = fetch(f"{api_url}/health", {})
if isinstance(health_payload, dict):
    core = health_payload.get("core", {})
    raw = core.get("providers", [])
    if isinstance(raw, list):
        providers = [str(provider).strip() for provider in raw if str(provider).strip()]

if not providers:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = fetch(f"{api_url}/api/agents/providers", headers)
    if isinstance(payload, dict):
        raw = payload.get("providers", [])
        if isinstance(raw, list):
            providers = [
                str(provider).strip() for provider in raw if str(provider).strip()
            ]

print(",".join(providers))
PY
}

check_results() {
  python3 - "$OUT_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print(f"[ERROR] results file not found: {path}", file=sys.stderr)
    raise SystemExit(1)

rows = []
with path.open("r", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

if not rows:
    print(f"[ERROR] results file is empty: {path}", file=sys.stderr)
    raise SystemExit(1)

successes = sum(1 for row in rows if row.get("ok"))
providers = sorted({str(row.get("provider", "")) for row in rows if row.get("provider")})

if successes == 0:
    print(
        "[ERROR] baseline eval completed but every request failed",
        file=sys.stderr,
    )
    raise SystemExit(1)

print(
    f"[INFO] successful requests: {successes}/{len(rows)} across providers: {', '.join(providers)}"
)
PY
}

load_api_key_from_env_file

PROVIDERS="${PROVIDERS:-$(discover_providers)}"
if [[ -z "$PROVIDERS" ]]; then
  echo "[WARN] provider auto-discovery failed; falling back to defaults: $DEFAULT_PROVIDERS"
  PROVIDERS="$DEFAULT_PROVIDERS"
else
  echo "[INFO] auto-detected providers: $PROVIDERS"
fi

echo "[INFO] validating dataset: $EVAL_FILE"
python3 training/scripts/validate_dataset.py "$EVAL_FILE"

echo "[INFO] running quick compare on providers: $PROVIDERS"
python3 training/scripts/run_baseline_eval.py \
  --eval "$EVAL_FILE" \
  --out "$OUT_FILE" \
  --summary "$SUMMARY_FILE" \
  --api-url "$API_URL" \
  --providers "$PROVIDERS" \
  --api-key "${MASCARADE_API_KEY:-}"

check_results

echo "[OK] quick comparison complete"
echo "     results: $OUT_FILE"
echo "     summary: $SUMMARY_FILE"
