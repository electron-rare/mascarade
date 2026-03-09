#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_ARGS=()
COMMAND_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/next_useful_lot.sh [options]

Resolve the next runnable lot for the current machine profile.

Options:
  --machine <name>
              Resolve runnable lots for a specific machine profile
  --machine-profiles <path>
              Use a specific machine profiles JSON file
  --all-scopes
              Ignore machine filtering and inspect all lots
  --json
              Return machine-readable output
  -h, --help  Show this help and exit
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --machine|--machine-profiles)
      [[ $# -ge 2 && -n "${2:-}" ]] || {
        echo "$1 expects a value" >&2
        usage >&2
        exit 2
      }
      GLOBAL_ARGS+=("$1" "$2")
      shift
      ;;
    --all-scopes)
      GLOBAL_ARGS+=("$1")
      ;;
    --json)
      COMMAND_ARGS+=("$1")
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      COMMAND_ARGS+=("$1")
      ;;
  esac
  shift
done

exec python3 "$ROOT_DIR/scripts/execution_hub.py" "${GLOBAL_ARGS[@]}" next "${COMMAND_ARGS[@]}"
