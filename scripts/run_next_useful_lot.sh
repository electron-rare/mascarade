#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WRITE_STATE=1
DRY_RUN=0
TARGET_LOT=""

usage() {
  cat <<'EOF'
Usage: bash scripts/run_next_useful_lot.sh [options]

Detect the next useful lot, run its canonical local checks, then refresh
docs/NEXT_USEFUL_LOT_STATE.md.

Options:
  --lot LOT      Force a specific lot id
  --dry-run      Print the checks instead of executing them
  --no-state     Skip writing docs/NEXT_USEFUL_LOT_STATE.md
  --help         Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lot)
      TARGET_LOT="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-state)
      WRITE_STATE=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

DETECT_ARGS=()
if [[ -n "$TARGET_LOT" ]]; then
  DETECT_ARGS+=(--lot "$TARGET_LOT")
fi

echo "== detect =="
bash "$ROOT_DIR/scripts/next_useful_lot.sh" detect "${DETECT_ARGS[@]}"
echo

echo "== checks =="
CHECK_STATUS=0
if [[ "$DRY_RUN" -eq 1 ]]; then
  bash "$ROOT_DIR/scripts/next_useful_lot.sh" checks --dry-run "${DETECT_ARGS[@]}" || CHECK_STATUS=$?
else
  bash "$ROOT_DIR/scripts/next_useful_lot.sh" checks "${DETECT_ARGS[@]}" || CHECK_STATUS=$?
fi
echo

if [[ "$WRITE_STATE" -eq 1 ]]; then
  echo "== state =="
  bash "$ROOT_DIR/scripts/next_useful_lot.sh" state --write "${DETECT_ARGS[@]}"
fi

exit "$CHECK_STATUS"
