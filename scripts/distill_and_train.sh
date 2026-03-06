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
        break
    fi
done

exec python finetune/distill_and_train.py "$@"
