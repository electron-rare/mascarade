#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KILL_LIFE_DIR="$(cd "$ROOT_DIR/../Kill_LIFE" && pwd)"
WRITE_STATE=1
DRY_RUN=0
TARGET_LOT=""
CHAIN=0
CHAIN_MAX=3

usage() {
  cat <<'EOF'
Usage: bash scripts/run_next_useful_lot.sh [options]

Detect the next useful lot, run its canonical local checks, then refresh
docs/NEXT_USEFUL_LOT_STATE.md.

Options:
  --lot LOT      Force a specific lot id
  --dry-run      Print the checks instead of executing them
  --no-state     Skip writing docs/NEXT_USEFUL_LOT_STATE.md
  --chain        Execute successive useful lots when possible
  --max-rounds N Limit chained executions (default 3)
  --help         Show this help
EOF
}

detect_lot() {
  local round=$1
  local -a detect_args=()
  if [[ -n "$TARGET_LOT" && "$round" -eq 1 ]]; then
    detect_args+=(--lot "$TARGET_LOT")
  fi
  bash "$ROOT_DIR/scripts/next_useful_lot.sh" detect "${detect_args[@]}"
}

run_checks_for_current() {
  local round=$1
  local -a check_args=()
  if [[ -n "$TARGET_LOT" && "$round" -eq 1 ]]; then
    check_args+=(--lot "$TARGET_LOT")
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    bash "$ROOT_DIR/scripts/next_useful_lot.sh" checks --dry-run "${check_args[@]}"
  else
    bash "$ROOT_DIR/scripts/next_useful_lot.sh" checks "${check_args[@]}"
  fi
}

sync_plan_todos_if_available() {
  local lot_id=$1
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return 0
  fi

  case "$lot_id" in
    kill-life-followup)
      if [[ -x "$KILL_LIFE_DIR/tools/run_autonomous_next_lots.sh" ]]; then
        bash "$KILL_LIFE_DIR/tools/run_autonomous_next_lots.sh" run
      else
        echo "Plan/todo sync skipped: Kill_LIFE script unavailable at $KILL_LIFE_DIR/tools/run_autonomous_next_lots.sh" >&2
      fi
      ;;
    *)
      :
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lot)
      if [[ $# -lt 2 ]]; then
        echo "Option --lot requires a lot id" >&2
        exit 2
      fi
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
    --chain)
      CHAIN=1
      shift
      ;;
    --max-rounds)
      if [[ $# -lt 2 ]]; then
        echo "--max-rounds requires a positive integer" >&2
        exit 2
      fi
      CHAIN_MAX="${2:-}"
      shift 2
      if ! [[ "$CHAIN_MAX" =~ ^[0-9]+$ ]] || [[ "$CHAIN_MAX" -lt 1 ]]; then
        echo "--max-rounds requires a positive integer" >&2
        exit 2
      fi
      CHAIN=1
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

ROUND=0
PREV_LOT_ID=""
CHECK_STATUS=0

while :; do
  ROUND=$((ROUND + 1))

  echo "== detect =="
  DETECT_OUTPUT="$(detect_lot "$ROUND")"
  echo "$DETECT_OUTPUT"

  LOT_ID="$(awk -F= '$1 == "lot_id" { print $2; exit }' <<<"$DETECT_OUTPUT")"
  if [[ -z "${LOT_ID:-}" ]]; then
    echo "Unable to detect lot id from output." >&2
    exit 2
  fi

  echo
  echo "== checks =="
  if run_checks_for_current "$ROUND"; then
    CHECK_STATUS=0
  else
    CHECK_STATUS=$?
  fi
  echo

  if [[ "$WRITE_STATE" -eq 1 ]]; then
    echo "== state =="
    state_args=()
    if [[ -n "$TARGET_LOT" && "$ROUND" -eq 1 ]]; then
      state_args+=(--lot "$TARGET_LOT")
    fi
    bash "$ROOT_DIR/scripts/next_useful_lot.sh" state --write \
      "${state_args[@]}"
  fi

  if [[ "$CHECK_STATUS" -eq 0 ]]; then
    sync_plan_todos_if_available "$LOT_ID"
  fi
  echo

  if [[ "$CHECK_STATUS" -ne 0 ]]; then
    break
  fi

  if [[ "$CHAIN" -eq 0 ]]; then
    break
  fi

  if [[ "$LOT_ID" == "external-only" ]]; then
    echo "No local useful lot remains."
    break
  fi

  if [[ "$ROUND" -ge "$CHAIN_MAX" ]]; then
    break
  fi

  if [[ -n "$PREV_LOT_ID" && "$LOT_ID" == "$PREV_LOT_ID" ]]; then
    echo "Lot unchanged after processing ($LOT_ID); stopping to avoid loop."
    break
  fi
  PREV_LOT_ID="$LOT_ID"
done

exit "$CHECK_STATUS"
