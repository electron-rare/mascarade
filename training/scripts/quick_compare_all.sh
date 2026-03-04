#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://localhost:3100}"
API_KEY="${MASCARADE_API_KEY:-}"
PROVIDERS="${PROVIDERS:-bedrock,openai,claude,google,mistral,huggingface}"
EVAL_FILE="${EVAL_FILE:-training/data/eval.sample.jsonl}"
OUT_FILE="${OUT_FILE:-training/output/baseline_results.quick.jsonl}"
SUMMARY_FILE="${SUMMARY_FILE:-training/output/baseline_summary.quick.md}"

echo "[INFO] validating dataset: $EVAL_FILE"
python3 training/scripts/validate_dataset.py "$EVAL_FILE"

echo "[INFO] running quick compare on providers: $PROVIDERS"
python3 training/scripts/run_baseline_eval.py \
  --eval "$EVAL_FILE" \
  --out "$OUT_FILE" \
  --summary "$SUMMARY_FILE" \
  --api-url "$API_URL" \
  --providers "$PROVIDERS" \
  --api-key "$API_KEY"

echo "[OK] quick comparison complete"
echo "     results: $OUT_FILE"
echo "     summary: $SUMMARY_FILE"
