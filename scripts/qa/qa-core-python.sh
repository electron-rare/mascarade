#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "ruff core modules critiques" "$PY" -m ruff check \
  "$ROOT/core/mascarade/finetune/orchestrator.py" \
  "$ROOT/core/mascarade/finetune/p2p/task_handlers.py" \
  "$ROOT/core/mascarade/agentic_rag.py" \
  "$ROOT/core/tests/test_finetune.py" \
  "$ROOT/core/tests/test_agentic_rag.py"

qa_run "pytest smoke core architecture" \
  "$PY" -m pytest \
  "$ROOT/core/tests/test_finetune.py" \
  "$ROOT/core/tests/test_agentic_rag.py" \
  "$ROOT/core/tests/test_rag.py" -q

if ! qa_fast; then
  qa_run "pytest core complément" \
    "$PY" -m pytest \
    "$ROOT/core/tests/test_router.py" \
    "$ROOT/core/tests/test_node_engine.py" \
    "$ROOT/core/tests/test_p2p_auth.py" -q
fi

echo "[OK] core python QA passed"
