#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CHAIN_SCRIPT="$ROOT_DIR/scripts/auto_chain_next_lots.sh"

LABEL="auto-next-lots"
REPORT_BASE="$ROOT_DIR/finetune/runs"
ITERATIONS="1"
MAX_CYCLES="0"
SLEEP_SECONDS="300"
MAX_SLEEP_SECONDS="1200"
BASE_SLEEP_SECONDS="300"
MAX_BLOCKED_STREAK="8"
MAX_FAILED_STREAK="2"
MAX_OK_CYCLES="0"
STOP_ON_NO_CANDIDATE=0
PASS_THROUGH_ARGS=()

ensure_positive_integer() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    die "$name must be a non-negative integer: $value"
  fi
}

usage() {
  cat <<'EOF'
Usage: ./scripts/auto_chain_next_lots_loop.sh [options]

Exécute automatiquement l'enchaînement auto des lots utiles.

Options:
  --label NAME                 Label prefixe des runs (default: auto-next-lots)
  --iterations N               Nombre de candidats à traiter par cycle (default: 1)
  --max-cycles N              Nombre max de cycles (0=infinite, default 0)
  --sleep-seconds N           Pause entre cycles en secondes (default: 300)
  --max-sleep-seconds N       Limite haute du backoff (default: 1200)
  --max-blocked-streak N       Arrêt après tant d'échecs bloqués consécutifs (default: 8)
  --max-failed-streak N        Arrêt après tant d'échecs non-bloqués consécutifs (default: 2)
  --max-ok-cycles N            Arrêt après N cycles avec au moins un ok (0=pas d'arrêt, default: 0)
  --stop-on-no-candidate       Stopper proprement quand plus de candidat n'est dispo
  --pass-through-arg "<arg>"   Arguments passés à auto_chain_next_lots.sh (can repeat)
  -h, --help                  Affiche l'aide
EOF
}

log() {
  printf '[auto-loop] %s\n' "$*"
}

die() {
  echo "auto-loop: $*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --label)
      [ "$#" -ge 2 ] || die "--label requires a value"
      LABEL="$2"
      shift 2
      ;;
    --iterations)
      [ "$#" -ge 2 ] || die "--iterations requires a value"
      ensure_positive_integer "--iterations" "$2"
      ITERATIONS="$2"
      shift 2
      ;;
    --max-cycles)
      [ "$#" -ge 2 ] || die "--max-cycles requires a value"
      ensure_positive_integer "--max-cycles" "$2"
      MAX_CYCLES="$2"
      shift 2
      ;;
    --sleep-seconds)
      [ "$#" -ge 2 ] || die "--sleep-seconds requires a value"
      ensure_positive_integer "--sleep-seconds" "$2"
      SLEEP_SECONDS="$2"
      BASE_SLEEP_SECONDS="$2"
      shift 2
      ;;
    --max-sleep-seconds)
      [ "$#" -ge 2 ] || die "--max-sleep-seconds requires a value"
      ensure_positive_integer "--max-sleep-seconds" "$2"
      MAX_SLEEP_SECONDS="$2"
      shift 2
      ;;
    --max-blocked-streak)
      [ "$#" -ge 2 ] || die "--max-blocked-streak requires a value"
      ensure_positive_integer "--max-blocked-streak" "$2"
      MAX_BLOCKED_STREAK="$2"
      shift 2
      ;;
    --max-failed-streak)
      [ "$#" -ge 2 ] || die "--max-failed-streak requires a value"
      ensure_positive_integer "--max-failed-streak" "$2"
      MAX_FAILED_STREAK="$2"
      shift 2
      ;;
    --max-ok-cycles)
      [ "$#" -ge 2 ] || die "--max-ok-cycles requires a value"
      ensure_positive_integer "--max-ok-cycles" "$2"
      MAX_OK_CYCLES="$2"
      shift 2
      ;;
    --stop-on-no-candidate)
      STOP_ON_NO_CANDIDATE=1
      shift
      ;;
    --pass-through-arg)
      [ "$#" -ge 2 ] || die "--pass-through-arg requires a value"
      if [ "$2" = "--report-dir" ]; then
        die "do not pass --report-dir to auto_chain_next_lots from loop. The loop controls cycle report directories."
      fi
      PASS_THROUGH_ARGS+=("$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      # Any unknown option is considered as a direct arg for auto_chain.
      PASS_THROUGH_ARGS+=("$1")
      shift
      ;;
  esac
done

command -v "$CHAIN_SCRIPT" >/dev/null 2>&1 || die "missing $CHAIN_SCRIPT"
if [ "$MAX_SLEEP_SECONDS" -lt "$BASE_SLEEP_SECONDS" ]; then
  MAX_SLEEP_SECONDS="$BASE_SLEEP_SECONDS"
fi

cycle=0
blocked_streak=0
failed_streak=0
ok_cycles=0
CURRENT_SLEEP_SECONDS="$SLEEP_SECONDS"

while true; do
  cycle=$((cycle + 1))
  if [ "$MAX_CYCLES" -gt 0 ] && [ "$cycle" -gt "$MAX_CYCLES" ]; then
    log "max cycles reached ($MAX_CYCLES). Stop."
    exit 0
  fi

  stamp="$(date +%Y%m%d_%H%M%S)"
  cycle_report_dir="$REPORT_BASE/${LABEL}_${stamp}_cycle_${cycle}"
  mkdir -p "$cycle_report_dir"
  log "cycle=$cycle report_dir=$cycle_report_dir"

  set +e
  "$CHAIN_SCRIPT" \
    --execute \
    --continue-on-error \
    --iterations "$ITERATIONS" \
    --report-dir "$cycle_report_dir" \
    "${PASS_THROUGH_ARGS[@]}" \
    > "$cycle_report_dir/loop-outer.log" \
    2>&1
  chain_rc=$?
  set -e

  if [ "$chain_rc" -ne 0 ] && ! [ -f "$cycle_report_dir/manifest.json" ]; then
    log "chain execution failed before manifest (rc=$chain_rc). Stop."
    exit "$chain_rc"
  fi

  if ! read ok blocked failed planned < <(python - <<'PY' "$cycle_report_dir/manifest.json"
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
except Exception:
    print("0 0 0 0")
    raise SystemExit(2)

for key in ("runs_ok", "runs_blocked", "runs_failed", "runs_planned"):
    print(payload.get(key, 0), end=" ")
print()
PY
); then
  log "manifest parse failed: $cycle_report_dir/manifest.json. Stop."
  exit 1
fi

if [ "$failed" -gt 0 ]; then
  failed_streak=$((failed_streak + 1))
  blocked_streak=0
  CURRENT_SLEEP_SECONDS="$BASE_SLEEP_SECONDS"
  log "cycle=$cycle failed_runs=$failed (streak=$failed_streak)"
  if [ "$failed_streak" -ge "$MAX_FAILED_STREAK" ]; then
    log "max failed streak reached ($failed_streak/$MAX_FAILED_STREAK). Stop."
    exit 1
  fi
else
  failed_streak=0
fi

if [ "$ok" -gt 0 ]; then
  ok_cycles=$((ok_cycles + 1))
  blocked_streak=0
  CURRENT_SLEEP_SECONDS="$BASE_SLEEP_SECONDS"
else
  blocked_streak=0
fi

if [ "$ok" -eq 0 ] && [ "$failed" -eq 0 ] && [ "$blocked" -gt 0 ]; then
  blocked_streak=$((blocked_streak + 1))
  CURRENT_SLEEP_SECONDS=$((CURRENT_SLEEP_SECONDS * 2))
  if [ "$CURRENT_SLEEP_SECONDS" -lt "$BASE_SLEEP_SECONDS" ]; then
    CURRENT_SLEEP_SECONDS="$BASE_SLEEP_SECONDS"
  fi
  if [ "$CURRENT_SLEEP_SECONDS" -gt "$MAX_SLEEP_SECONDS" ]; then
    CURRENT_SLEEP_SECONDS="$MAX_SLEEP_SECONDS"
  fi
  log "cycle=$cycle blocked_runs=$blocked (blocked streak=$blocked_streak)"
  if [ "$blocked_streak" -ge "$MAX_BLOCKED_STREAK" ]; then
    log "max blocked streak reached ($blocked_streak/$MAX_BLOCKED_STREAK). Stop."
    exit 2
  fi
elif [ "$ok" -eq 0 ] && [ "$failed" -eq 0 ] && [ "$planned" -gt 0 ]; then
  CURRENT_SLEEP_SECONDS="$BASE_SLEEP_SECONDS"
fi

if [ "$ok" -eq 0 ] && [ "$failed" -eq 0 ] && [ "$planned" -gt 0 ]; then
  if [ "$STOP_ON_NO_CANDIDATE" -eq 1 ]; then
    log "no candidate planned/ran this cycle. Stop."
    exit 0
  fi
  log "cycle=$cycle no-op (planned only)."
fi

if [ "$MAX_OK_CYCLES" -gt 0 ] && [ "$ok_cycles" -ge "$MAX_OK_CYCLES" ]; then
  log "max ok cycles reached ($ok_cycles/$MAX_OK_CYCLES). Stop."
  exit 0
fi

if [ "$CURRENT_SLEEP_SECONDS" -gt 0 ]; then
  log "sleep $CURRENT_SLEEP_SECONDS s before next cycle."
  sleep "$CURRENT_SLEEP_SECONDS"
fi
done
