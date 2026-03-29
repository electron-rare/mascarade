#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PY="$(python_cmd)"

qa_run "router tests coeur" \
  "$PY" -m pytest \
  "$ROOT/core/tests/test_router.py" \
  "$ROOT/core/tests/test_router_domain_routing.py" \
  "$ROOT/core/tests/test_routers_health.py" \
  "$ROOT/core/tests/test_routers_chat.py" -q

if ! qa_fast; then
  qa_run "router tests étendus" \
    "$PY" -m pytest \
    "$ROOT/core/tests/test_routers_agents.py" \
    "$ROOT/core/tests/test_routers_providers.py" \
    "$ROOT/core/tests/test_admin_router.py" -q
fi

echo "[OK] router QA passed"
