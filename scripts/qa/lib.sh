#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
FAST_MODE="${FAST_MODE:-false}"

qa_info() {
  echo "[INFO] $*"
}

qa_skip() {
  echo "[SKIP] $*"
}

qa_run() {
  local label="$1"
  shift
  echo "[RUN] ${label}"
  "$@"
}

qa_fast() {
  [[ "${FAST_MODE}" == "true" ]]
}

python_cmd() {
  if [[ -x "$ROOT/core/.venv/bin/python" ]]; then
    echo "$ROOT/core/.venv/bin/python"
  else
    echo "python3"
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    qa_skip "commande absente: $cmd"
    return 1
  fi
  return 0
}
