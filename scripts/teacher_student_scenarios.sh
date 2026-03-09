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
    FOUND_VENV=1
    break
  fi
done

if [ "${FOUND_VENV:-0}" -ne 1 ]; then
  echo "No fine-tuning virtualenv found." >&2
  echo "Run ./scripts/bootstrap_finetune_env.sh first." >&2
  exit 1
fi

exec python finetune/batch_scenarios.py "$@"
