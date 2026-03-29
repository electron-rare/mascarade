#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "node-engine tests coeur" \
  "$PY" -m pytest \
  "$ROOT/core/tests/test_node_engine.py" \
  "$ROOT/core/tests/test_node_engine_types.py" \
  "$ROOT/core/tests/test_node_engine_graph.py" -q

if ! qa_fast; then
  qa_run "node-engine tests parallélisme/e2e" \
    "$PY" -m pytest \
    "$ROOT/core/tests/test_node_engine_parallel.py" \
    "$ROOT/core/tests/test_node_engine_e2e.py" -q
fi

echo "[OK] node-engine QA passed"
