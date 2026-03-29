#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "p2p tests essentiels" \
  "$PY" -m pytest \
  "$ROOT/core/tests/test_p2p_auth.py" \
  "$ROOT/core/tests/test_p2p_identity.py" \
  "$ROOT/core/tests/test_p2p_tasks.py" \
  "$ROOT/core/tests/test_p2p_provider.py" -q

if ! qa_fast; then
  qa_run "p2p tests étendus" "$PY" -m pytest "$ROOT/core/tests/test_p2p_"*".py" -q
fi

echo "[OK] p2p QA passed"
