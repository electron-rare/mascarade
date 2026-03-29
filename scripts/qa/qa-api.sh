#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

if ! require_cmd npm; then
  exit 0
fi

if [[ ! -d "$ROOT/api/node_modules" ]]; then
  qa_skip "api/node_modules absent, skip build/tests API"
  exit 0
fi

qa_run "api build" bash -lc "cd '$ROOT/api' && npm run build"

if ! qa_fast; then
  qa_run "api tests" bash -lc "cd '$ROOT/api' && npm test"
fi

echo "[OK] api QA passed"
