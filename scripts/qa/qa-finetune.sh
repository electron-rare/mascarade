#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "finetune tests principaux" \
  "$PY" -m pytest \
  "$ROOT/core/tests/test_finetune.py" \
  "$ROOT/core/tests/test_finetune_pipeline.py" \
  "$ROOT/core/tests/test_finetune_publish.py" \
  "$ROOT/core/tests/test_rlvr.py" -q

if ! qa_fast; then
  qa_run "finetune lint critique" "$PY" -m ruff check "$ROOT/core/mascarade/finetune"
fi

echo "[OK] finetune QA passed"
