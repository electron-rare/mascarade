#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_ARGS=()
COMMAND_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --machine|--machine-profiles)
      [[ $# -ge 2 && -n "${2:-}" ]] || {
        echo "$1 expects a value" >&2
        exit 2
      }
      GLOBAL_ARGS+=("$1" "$2")
      shift
      ;;
    --all-scopes)
      GLOBAL_ARGS+=("$1")
      ;;
    *)
      COMMAND_ARGS+=("$1")
      ;;
  esac
  shift
done

exec python3 "$ROOT_DIR/scripts/execution_hub.py" "${GLOBAL_ARGS[@]}" context "${COMMAND_ARGS[@]}"
