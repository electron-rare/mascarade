#!/usr/bin/env bash
# scripts/qa/qa-docs.sh — QA docs + registre TODO
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 "$ROOT/scripts/qa/validate_todo_registry.py"
python3 "$ROOT/scripts/qa/validate_doc_coherence.py"
python3 "$ROOT/scripts/qa/validate_observability_consolidation.py"

echo "[OK] docs QA passed"
