#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

. "$ROOT_DIR/scripts/llm_env.sh"

WATCH_REFRESH=1
WATCH_BENCH=1
PRUNE_MODELS=1
CAD_SMOKE=1
COMPONENTS_REVIEW=1
CONTINUE_ON_ERROR=0
EXECUTE=0
APPLY_PRUNE=0
VERBOSE=0
LABEL="next-lots"
REPORT_DIR=""

usage() {
  cat <<'EOF'
Usage: ./scripts/next_finetune_lots.sh [options]

Chain the current next useful fine-tuning lots:
  1. Refresh model watch + student selection
  2. Plan or run the first student_watch benchmark
  3. Report or prune cached models that were not validated
  4. Run CAD/EDA + KiCad MCP tool smoke in tmpfs
  5. Show components review status

Options:
  --label NAME             Label prefix for generated artifacts (default: next-lots)
  --report-dir PATH        Directory used for logs + summary (default: finetune/runs/<label>_<stamp>)
  --skip-watch             Skip model watch refresh
  --skip-watch-bench       Skip watch candidate benchmark planning
  --skip-prune             Skip unvalidated model cache pruning report
  --skip-cad-smoke         Skip CAD/EDA tmpfs smoke
  --skip-components-review Skip components review status
  --execute                Run the watch benchmark instead of dry-run only
  --apply-prune            Apply cache deletion for rejected/pending_review models
  --continue-on-error      Keep running later lots if one step fails
  --verbose                Print executed commands
  -h, --help               Show this help
EOF
}

log() {
  printf '[next-lots] %s\n' "$*"
}

write_summary() {
  mkdir -p "$REPORT_DIR"
  cat >"$REPORT_DIR/summary.json" <<EOF
{
  "generated_at": "$(date +%Y-%m-%dT%H:%M:%S)",
  "label": "$LABEL",
  "report_dir": "$REPORT_DIR",
  "execute": $EXECUTE,
  "apply_prune": $APPLY_PRUNE,
  "continue_on_error": $CONTINUE_ON_ERROR,
  "watch_refresh": "$WATCH_REFRESH_STATUS",
  "watch_bench": "$WATCH_BENCH_STATUS",
  "prune": "$PRUNE_STATUS",
  "cad_smoke": "$CAD_STATUS",
  "components_review": "$COMPONENTS_STATUS",
  "logs": {
    "watch_refresh": "$REPORT_DIR/watch-refresh.log",
    "watch_bench": "$REPORT_DIR/watch-bench.log",
    "prune": "$REPORT_DIR/prune-unvalidated.log",
    "cad_smoke": "$REPORT_DIR/cad-tool-smoke.log",
    "components_review": "$REPORT_DIR/components-review.log"
  }
}
EOF
}

run() {
  if [ "$VERBOSE" -eq 1 ]; then
    printf '[next-lots][cmd] %s\n' "$*" >&2
  fi
  "$@"
}

activate_venv() {
  local venv
  for venv in \
    "$ROOT_DIR/finetune/.venv/bin/activate" \
    "$ROOT_DIR/venv_tuning/bin/activate"
  do
    if [ -f "$venv" ]; then
      # shellcheck disable=SC1090
      source "$venv"
      return 0
    fi
  done
  echo "No fine-tuning virtualenv found. Run ./scripts/bootstrap_finetune_env.sh first." >&2
  return 1
}

step() {
  local name="$1"
  local status_var="$2"
  local log_file="$REPORT_DIR/${name}.log"
  shift 2
  mkdir -p "$REPORT_DIR"
  log "step=$name"
  if "$@" >"$log_file" 2>&1; then
    cat "$log_file"
    log "step=$name status=ok"
    printf -v "$status_var" '%s' "ok"
    write_summary
    return 0
  fi
  cat "$log_file"
  log "step=$name status=failed"
  printf -v "$status_var" '%s' "failed"
  write_summary
  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --label)
      [ "$#" -ge 2 ] || { echo "--label requires a value" >&2; exit 2; }
      LABEL="$2"
      shift 2
      ;;
    --report-dir)
      [ "$#" -ge 2 ] || { echo "--report-dir requires a value" >&2; exit 2; }
      REPORT_DIR="$2"
      shift 2
      ;;
    --skip-watch)
      WATCH_REFRESH=0
      shift
      ;;
    --skip-watch-bench)
      WATCH_BENCH=0
      shift
      ;;
    --skip-prune)
      PRUNE_MODELS=0
      shift
      ;;
    --skip-cad-smoke)
      CAD_SMOKE=0
      shift
      ;;
    --skip-components-review)
      COMPONENTS_REVIEW=0
      shift
      ;;
    --execute)
      EXECUTE=1
      shift
      ;;
    --apply-prune)
      APPLY_PRUNE=1
      shift
      ;;
    --continue-on-error)
      CONTINUE_ON_ERROR=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
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
done

activate_venv

STAMP="$(date +%Y%m%d_%H%M%S)"
if [ -z "$REPORT_DIR" ]; then
  REPORT_DIR="$ROOT_DIR/finetune/runs/${LABEL}_${STAMP}"
fi
mkdir -p "$(dirname "$REPORT_DIR")"
REPORT_DIR="$(cd "$(dirname "$REPORT_DIR")" && pwd)/$(basename "$REPORT_DIR")"
mkdir -p "$REPORT_DIR"

FAILED=0
WATCH_REFRESH_STATUS="skipped"
WATCH_BENCH_STATUS="skipped"
PRUNE_STATUS="skipped"
CAD_STATUS="skipped"
COMPONENTS_STATUS="skipped"

log "llm_root=$MASCARADE_LLM_DIR"
log "hf_cache=$HUGGINGFACE_HUB_CACHE"
log "report_dir=$REPORT_DIR"
write_summary

if [ "$WATCH_REFRESH" -eq 1 ]; then
  if ! step "watch-refresh" WATCH_REFRESH_STATUS run python finetune/model_selector.py --watch --refresh --task code --watch-top 8 --top 6 --auto; then
    FAILED=1
    [ "$CONTINUE_ON_ERROR" -eq 1 ] || exit 1
  fi
fi

if [ "$WATCH_BENCH" -eq 1 ]; then
  WATCH_BENCH_CMD=(
    bash
    "$ROOT_DIR/scripts/bench_watch_candidate.sh"
    --domain stm32
    --seq-len 512
    --max-samples 16
    --epochs 1
    --tokenize-workers 1
    --run-label "$LABEL-watch"
  )
  if [ "$EXECUTE" -eq 1 ]; then
    WATCH_BENCH_CMD+=(--execute)
  fi
  if ! step "watch-bench" WATCH_BENCH_STATUS run "${WATCH_BENCH_CMD[@]}"; then
    FAILED=1
    [ "$CONTINUE_ON_ERROR" -eq 1 ] || exit 1
  fi
fi

if [ "$PRUNE_MODELS" -eq 1 ]; then
  PRUNE_CMD=(
    python
    finetune/model_selector.py
    --prune-unvalidated
  )
  if [ "$APPLY_PRUNE" -eq 1 ]; then
    PRUNE_CMD+=(--yes)
  fi
  if ! step "prune-unvalidated" PRUNE_STATUS run "${PRUNE_CMD[@]}"; then
    FAILED=1
    [ "$CONTINUE_ON_ERROR" -eq 1 ] || exit 1
  fi
fi

if [ "$CAD_SMOKE" -eq 1 ]; then
  if ! step "cad-tool-smoke" CAD_STATUS run "$ROOT_DIR/scripts/cad_tool_smoke_tmpfs.sh" --label "$LABEL-cad"; then
    FAILED=1
    [ "$CONTINUE_ON_ERROR" -eq 1 ] || exit 1
  fi
fi

if [ "$COMPONENTS_REVIEW" -eq 1 ]; then
  if ! step "components-review" COMPONENTS_STATUS run python finetune/promotion_utils.py status components; then
    FAILED=1
    [ "$CONTINUE_ON_ERROR" -eq 1 ] || exit 1
  fi
fi

write_summary
log "summary=$REPORT_DIR/summary.json"
exit "$FAILED"
