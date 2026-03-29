#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "orchestrator tests ciblés" \
  "$PY" -m pytest "$ROOT/core/tests/test_finetune.py" -k "TestOrchestrator or phase_dpo or train_alignment" -q

if ! qa_fast; then
  qa_run "orchestrator node engine graph" \
    "$PY" -m pytest \
    "$ROOT/core/tests/test_node_engine_graph.py" \
    "$ROOT/core/tests/test_node_engine_toposort.py" -q
fi

echo "[OK] orchestrator QA passed"
