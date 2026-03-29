#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "agents tests coeur" \
  "$PY" -m pytest \
  "$ROOT/core/tests/test_agents.py" \
  "$ROOT/core/tests/test_agent_delegation.py" \
  "$ROOT/core/tests/test_agent_gates.py" -q

if ! qa_fast; then
  qa_run "agents tests cli + copilot" \
    "$PY" -m pytest \
    "$ROOT/core/tests/test_cli_agents.py" \
    "$ROOT/core/tests/test_copilot_agent.py" -q
fi

echo "[OK] agents QA passed"
