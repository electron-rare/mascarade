#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HUB_FILE="$ROOT_DIR/docs/EXECUTION_HUB.md"
START_LOT=false
JSON_OUTPUT=false
FORWARD_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/chain_next_lot.sh [options]

Refresh the execution hub, resolve the next runnable lot, and optionally
mark it as IN_PROGRESS.

Options:
  --start     Mark the selected lot as IN_PROGRESS and append a journal note
  --json      Print the selected lot as JSON
  --machine <name>
              Resolve runnable lots for a specific machine profile
  --machine-profiles <path>
              Use a specific machine profiles JSON file
  --all-scopes
              Ignore machine filtering and inspect all lots
  -h, --help  Show this help and exit
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start)
      START_LOT=true
      ;;
    --json)
      JSON_OUTPUT=true
      ;;
    --machine|--machine-profiles)
      [[ $# -ge 2 && -n "${2:-}" ]] || {
        echo "$1 expects a value" >&2
        usage >&2
        exit 2
      }
      FORWARD_ARGS+=("$1" "$2")
      shift
      ;;
    --all-scopes)
      FORWARD_ARGS+=("$1")
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

python3 "$ROOT_DIR/scripts/execution_hub.py" --hub "$HUB_FILE" "${FORWARD_ARGS[@]}" refresh

if ! NEXT_JSON="$(python3 "$ROOT_DIR/scripts/execution_hub.py" --hub "$HUB_FILE" "${FORWARD_ARGS[@]}" next --json)"; then
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    printf '%s\n' "${NEXT_JSON:-{\"ok\":false}}"
  else
    printf 'Aucun lot runnable detecte automatiquement.\n'
  fi
  exit 3
fi

if [[ "$START_LOT" == "true" ]]; then
  read -r LOT_ID MACHINE_NAME < <(python3 - "$NEXT_JSON" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
print(payload["runnable"]["id"], payload.get("machine", "unknown-machine"))
PY
)
  python3 "$ROOT_DIR/scripts/execution_hub.py" \
    --hub "$HUB_FILE" \
    "${FORWARD_ARGS[@]}" \
    set-status \
    --id "$LOT_ID" \
    --status IN_PROGRESS \
    --refresh \
    --journal "lot ${LOT_ID} passe automatiquement a IN_PROGRESS via scripts/chain_next_lot.sh sur ${MACHINE_NAME}"
  NEXT_JSON="$(python3 "$ROOT_DIR/scripts/execution_hub.py" --hub "$HUB_FILE" "${FORWARD_ARGS[@]}" next --json)"
fi

if [[ "$JSON_OUTPUT" == "true" ]]; then
  printf '%s\n' "$NEXT_JSON"
  exit 0
fi

python3 - "$NEXT_JSON" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
lot = payload["runnable"]
print(f"id: {lot['id']}")
print(f"repo: {lot['repo']}")
print(f"status: {lot['status']}")
print(f"title: {lot['title']}")
print(f"depend: {lot['depend']}")
print(f"validation: {lot['validation']}")
PY
