#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "rag tests essentiels" \
  "$PY" -m pytest \
  "$ROOT/core/tests/test_rag.py" \
  "$ROOT/core/tests/test_agentic_rag.py" \
  "$ROOT/core/tests/test_rag_chunker.py" -q

if ! qa_fast; then
  qa_run "rag tests bibliothèque" "$PY" -m pytest "$ROOT/core/tests/test_rag_library.py" -q
fi

echo "[OK] rag QA passed"
