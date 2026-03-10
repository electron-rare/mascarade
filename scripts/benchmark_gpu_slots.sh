#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

for VENV in \
  "$ROOT_DIR/finetune/.venv/bin/activate" \
  "$ROOT_DIR/venv_tuning/bin/activate"
do
  if [ -f "$VENV" ]; then
    # shellcheck disable=SC1090
    source "$VENV"
    exec python finetune/benchmark_gpu_slots.py "$@"
  fi
done

echo "No fine-tuning virtualenv found." >&2
echo "Run ./scripts/bootstrap_finetune_env.sh first." >&2
exit 1
