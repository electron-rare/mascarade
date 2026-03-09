#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_ARGS=()
COMMAND_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/machine_lot_matrix.sh [options]

Show the next useful lot for each known machine profile.

Options:
  --machine <name>
              Ensure a given machine profile is present in the output
  --machine-profiles <path>
              Use a specific machine profiles JSON file
  --all-scopes
              Ignore machine filtering inside each profile
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

exec python3 "$ROOT_DIR/scripts/execution_hub.py" "${GLOBAL_ARGS[@]}" matrix "${COMMAND_ARGS[@]}"
