#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

if qa_fast; then
  qa_skip "FAST_MODE actif: e2e complet ignoré"
  exit 0
fi

if [[ -f "$ROOT/scripts/run-e2e-tests.sh" ]]; then
  qa_run "e2e script principal" bash -lc "cd '$ROOT' && bash scripts/run-e2e-tests.sh"
elif [[ -f "$ROOT/e2e-verification.sh" ]]; then
  qa_run "e2e fallback" bash -lc "cd '$ROOT' && bash e2e-verification.sh"
else
  qa_skip "aucun script e2e trouvé"
fi

echo "[OK] e2e QA passed"
