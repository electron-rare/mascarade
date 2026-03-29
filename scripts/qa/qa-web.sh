#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

if ! require_cmd npm; then
  exit 0
fi

if [[ ! -d "$ROOT/web/node_modules" ]]; then
  qa_skip "web/node_modules absent, skip build/tests Web"
  exit 0
fi

qa_run "web build" bash -lc "cd '$ROOT/web' && npm run build"

if ! qa_fast; then
  qa_run "web tests" bash -lc "cd '$ROOT/web' && npm test -- --run"
fi

echo "[OK] web QA passed"
