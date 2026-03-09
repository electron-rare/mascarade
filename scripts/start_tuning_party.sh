#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/lib.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/tuning_party_common.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/start_tuning_party.sh [options]

Point d'entree operateur pour la tuning party locale.

Par defaut le script:
  1. prepare le prochain lot utile
  2. lance la boucle watch en arriere-plan
  3. lance le pipeline complet avec monitoring

Options:
  --background             Lance la session en arriere-plan puis rend la main
  --prepare-only           Execute uniquement la preparation initiale
  --watch-only             Execute uniquement la boucle watch
  --pipeline-only          Execute uniquement le pipeline complet
  --skip-prepare           Ne pas executer next_finetune_lots au debut
  --skip-watch             Ne pas lancer la boucle watch
  --skip-pipeline          Ne pas lancer le pipeline complet
  --foreground-watch       Lancer la boucle watch au premier plan
  --watch-sleep N          Pause initiale/backoff de base pour la boucle watch (default: 600)
  --watch-max-sleep N      Backoff max pour la boucle watch (default: 1800)
  --watch-max-blocked N    Nombre max de blocages consecutifs (default: 12)
  --watch-max-failed N     Nombre max d'echecs non bloques consecutifs (default: 3)
  --watch-max-ok N         Arret apres N cycles avec succes (default: 1)
  --watch-label NAME       Prefixe des runs watch (default: auto-next-lots-live)
  --monitor-interval N     Intervalle de monitoring pipeline en secondes (default: 15)
  --pipeline-arg ARG       Argument transmis a finetune/batch_full_pipeline.sh (repeatable)
  --domain NAME            Domaine principal de session pour metadata/TUI
  --skip-auto-refresh-missing
                          Ne pas rafraichir automatiquement les briefs dataset research manquants
  --label NAME             Label global de session (default: tuning-party)
  --verbose                Affiche monitoring + extraits de logs
  -h, --help               Affiche l'aide
EOF
}

log() {
  printf '[start-tuning-party] %s\n' "$*"
}

die() {
  echo "start-tuning-party: $*" >&2
  exit 1
}

ensure_positive_integer() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    die "$name must be a non-negative integer: $value"
  fi
}

resolve_session_domain() {
  if [ -n "${SESSION_DOMAIN:-}" ]; then
    printf '%s\n' "$SESSION_DOMAIN"
    return 0
  fi

  if [ -n "${DOMAIN:-}" ]; then
    printf '%s\n' "$DOMAIN"
    return 0
  fi

  local i=0 token next csv first
  while [ $i -lt ${#PIPELINE_ARGS[@]} ]; do
    token="${PIPELINE_ARGS[$i]}"
    next=""
    if [ $((i + 1)) -lt ${#PIPELINE_ARGS[@]} ]; then
      next="${PIPELINE_ARGS[$((i + 1))]}"
    fi
    case "$token" in
      --domain)
        [ -n "$next" ] && printf '%s\n' "$next" && return 0
        ;;
      --domains)
        if [ -n "$next" ]; then
          csv="${next// /}"
          first="${csv%%,*}"
          [ -n "$first" ] && printf '%s\n' "$first" && return 0
        fi
        ;;
    esac
    i=$((i + 1))
  done

  if [ "$PIPELINE" -eq 1 ]; then
    printf 'all\n'
  elif [ "$WATCH" -eq 1 ] || [ "$PREPARE" -eq 1 ]; then
    printf 'stm32\n'
  else
    printf 'unknown\n'
  fi
}

resolve_pipeline_domains() {
  if [ -n "${PIPELINE_DOMAINS:-}" ]; then
    printf '%s\n' "$PIPELINE_DOMAINS"
    return 0
  fi

  if [ -n "${SESSION_DOMAIN:-}" ]; then
    printf '%s\n' "$SESSION_DOMAIN"
    return 0
  fi

  local i=0 token next
  while [ $i -lt ${#PIPELINE_ARGS[@]} ]; do
    token="${PIPELINE_ARGS[$i]}"
    next=""
    if [ $((i + 1)) -lt ${#PIPELINE_ARGS[@]} ]; then
      next="${PIPELINE_ARGS[$((i + 1))]}"
    fi
    case "$token" in
      --domains)
        [ -n "$next" ] && printf '%s\n' "$next" && return 0
        ;;
      --domain)
        [ -n "$next" ] && printf '%s\n' "$next" && return 0
        ;;
    esac
    i=$((i + 1))
  done

  if [ "$PIPELINE" -eq 1 ]; then
    printf 'stm32,freecad,iot,dsp,kicad,emc,platformio,embedded,power,spice\n'
  else
    printf '%s\n' "$(resolve_session_domain)"
  fi
}

pipeline_args_have_domain_selector() {
  local token
  for token in "${PIPELINE_ARGS[@]}"; do
    case "$token" in
      --domain|--domains)
        return 0
        ;;
    esac
  done
  return 1
}

canonicalize_session_scope() {
  DOMAIN="$(resolve_session_domain)"
  PIPELINE_DOMAINS="$(resolve_pipeline_domains)"

  if ! pipeline_args_have_domain_selector && [ -n "$PIPELINE_DOMAINS" ]; then
    PIPELINE_ARGS=(--domains "$PIPELINE_DOMAINS" "${PIPELINE_ARGS[@]}")
  fi

  export DOMAIN
  export PIPELINE_DOMAINS
}

write_meta() {
  cat >"$META_FILE" <<EOF
LABEL=$LABEL
DOMAIN=$DOMAIN
PIPELINE_DOMAINS=$PIPELINE_DOMAINS
SESSION_DIR=$SESSION_DIR
PREPARE_LOG=$PREPARE_LOG
WATCH_LOG=$WATCH_LOG
PIPELINE_LOG=$PIPELINE_LOG
AUTO_REFRESH_LOG=$AUTO_REFRESH_LOG
WATCH_PID_FILE=$WATCH_PID_FILE
PIPELINE_PID_FILE=$PIPELINE_PID_FILE
WATCH_LABEL=$WATCH_LABEL
PREPARE_ENABLED=$PREPARE
WATCH_ENABLED=$WATCH
PIPELINE_ENABLED=$PIPELINE
EOF
}

print_step() {
  local current="$1"
  local total="$2"
  local label="$3"
  step_progress "$current" "$total" "$label"
}

show_runtime_snapshot() {
  local phase current total gpu_state watch_state
  IFS='|' read -r phase current total < <(tuning_party_pipeline_phase "$PIPELINE_LOG")
  gpu_state="$(tuning_party_gpu_summary)"
  watch_state="$(tuning_party_watch_state "$WATCH_LOG")"
  info "Pipeline : $phase $(tuning_party_bar "$current" "$total" 18)"
  info "Watch    : $watch_state"
  info "GPU      : $gpu_state"
}

show_log_excerpt() {
  local title="$1"
  local log_file="$2"
  [ -f "$log_file" ] || return 0
  info "$title: $(basename "$log_file")"
  tail -n 5 "$log_file" | sed 's/^/    /'
}

monitor_pipeline() {
  local pid="$1"
  local interval="$2"

  while tuning_party_pid_alive "$pid"; do
    section "Tuning Party Monitor"
    show_runtime_snapshot
    if [ "$VERBOSE" -eq 1 ]; then
      show_log_excerpt "Watch tail" "$WATCH_LOG"
      show_log_excerpt "Pipeline tail" "$PIPELINE_LOG"
    fi
    sleep "$interval"
  done
}

resolve_refresh_domains_csv() {
  if [ -n "${PIPELINE_DOMAINS:-}" ] && [ "${PIPELINE_DOMAINS:-}" != "unknown" ]; then
    printf '%s\n' "$PIPELINE_DOMAINS"
    return 0
  fi
  if [ -n "${DOMAIN:-}" ] && [ "${DOMAIN:-}" != "unknown" ]; then
    printf '%s\n' "$DOMAIN"
    return 0
  fi
  printf 'stm32\n'
}

missing_research_domains() {
  python - "$ROOT_DIR" "$1" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
domains_csv = sys.argv[2].strip()
domains = [item.strip() for item in domains_csv.split(",") if item.strip()]
research_dir = root / "finetune" / "research"
missing = []
for domain in domains:
    if domain in {"all", "unknown"}:
        continue
    if not (research_dir / f"{domain}_refresh.json").exists():
        missing.append(domain)
print(" ".join(missing))
PY
}

run_auto_refresh_missing() {
  local domains_csv="$1"
  local missing_list domain failed=0
  missing_list="$(missing_research_domains "$domains_csv")"
  if [ -z "$missing_list" ]; then
    log "dataset_research=already-present domains=$domains_csv"
    return 0
  fi
  log "dataset_research=refresh-missing domains=$missing_list"
  : >"$AUTO_REFRESH_LOG"
  for domain in $missing_list; do
    {
      echo "[dataset-refresh] domain=$domain"
      (
        cd "$ROOT_DIR"
        python finetune/dataset_refresh.py "$domain" --with-hf
      )
      echo "[dataset-refresh] domain=$domain status=ok"
    } >>"$AUTO_REFRESH_LOG" 2>&1 || {
      echo "[dataset-refresh] domain=$domain status=failed" >>"$AUTO_REFRESH_LOG"
      failed=$((failed + 1))
    }
  done
  if [ "$failed" -gt 0 ]; then
    log "dataset_research=partial failures=$failed log=$AUTO_REFRESH_LOG"
  else
    log "dataset_research=completed log=$AUTO_REFRESH_LOG"
  fi
}

PREPARE=1
WATCH=1
PIPELINE=1
BACKGROUND=0
FOREGROUND_WATCH=0
VERBOSE=0
AUTO_REFRESH_MISSING=1
WATCH_SLEEP_SECONDS="600"
WATCH_MAX_SLEEP_SECONDS="1800"
WATCH_MAX_BLOCKED_STREAK="12"
WATCH_MAX_FAILED_STREAK="3"
WATCH_MAX_OK_CYCLES="1"
WATCH_LABEL="auto-next-lots-live"
MONITOR_INTERVAL="15"
LABEL="tuning-party"
SESSION_DIR=""
SESSION_DOMAIN="${DOMAIN:-}"
PIPELINE_DOMAINS="${PIPELINE_DOMAINS:-}"
PIPELINE_ARGS=()
INTERNAL_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      PREPARE=1
      WATCH=0
      PIPELINE=0
      shift
      ;;
    --background)
      BACKGROUND=1
      shift
      ;;
    --watch-only)
      PREPARE=0
      WATCH=1
      PIPELINE=0
      shift
      ;;
    --pipeline-only)
      PREPARE=0
      WATCH=0
      PIPELINE=1
      shift
      ;;
    --skip-prepare)
      PREPARE=0
      shift
      ;;
    --skip-watch)
      WATCH=0
      shift
      ;;
    --skip-pipeline)
      PIPELINE=0
      shift
      ;;
    --foreground-watch)
      FOREGROUND_WATCH=1
      shift
      ;;
    --watch-sleep)
      [ "$#" -ge 2 ] || die "--watch-sleep requires a value"
      ensure_positive_integer "--watch-sleep" "$2"
      WATCH_SLEEP_SECONDS="$2"
      shift 2
      ;;
    --watch-max-sleep)
      [ "$#" -ge 2 ] || die "--watch-max-sleep requires a value"
      ensure_positive_integer "--watch-max-sleep" "$2"
      WATCH_MAX_SLEEP_SECONDS="$2"
      shift 2
      ;;
    --watch-max-blocked)
      [ "$#" -ge 2 ] || die "--watch-max-blocked requires a value"
      ensure_positive_integer "--watch-max-blocked" "$2"
      WATCH_MAX_BLOCKED_STREAK="$2"
      shift 2
      ;;
    --watch-max-failed)
      [ "$#" -ge 2 ] || die "--watch-max-failed requires a value"
      ensure_positive_integer "--watch-max-failed" "$2"
      WATCH_MAX_FAILED_STREAK="$2"
      shift 2
      ;;
    --watch-max-ok)
      [ "$#" -ge 2 ] || die "--watch-max-ok requires a value"
      ensure_positive_integer "--watch-max-ok" "$2"
      WATCH_MAX_OK_CYCLES="$2"
      shift 2
      ;;
    --watch-label)
      [ "$#" -ge 2 ] || die "--watch-label requires a value"
      WATCH_LABEL="$2"
      shift 2
      ;;
    --monitor-interval)
      [ "$#" -ge 2 ] || die "--monitor-interval requires a value"
      ensure_positive_integer "--monitor-interval" "$2"
      MONITOR_INTERVAL="$2"
      shift 2
      ;;
    --pipeline-arg)
      [ "$#" -ge 2 ] || die "--pipeline-arg requires a value"
      PIPELINE_ARGS+=("$2")
      shift 2
      ;;
    --label)
      [ "$#" -ge 2 ] || die "--label requires a value"
      LABEL="$2"
      shift 2
      ;;
    --domain)
      [ "$#" -ge 2 ] || die "--domain requires a value"
      SESSION_DOMAIN="$2"
      shift 2
      ;;
    --skip-auto-refresh-missing)
      AUTO_REFRESH_MISSING=0
      shift
      ;;
    --session-dir)
      [ "$#" -ge 2 ] || die "--session-dir requires a value"
      SESSION_DIR="$2"
      shift 2
      ;;
    --run-session)
      INTERNAL_RUN=1
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
      die "unknown option: $1"
      ;;
  esac
done

if [ "$PREPARE" -eq 0 ] && [ "$WATCH" -eq 0 ] && [ "$PIPELINE" -eq 0 ]; then
  die "nothing to do; enable at least one stage"
fi

activate_tui
[ -t 1 ] && banner

. "$ROOT_DIR/scripts/llm_env.sh"

if [ -f "$ROOT_DIR/venv_tuning/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/venv_tuning/bin/activate"
else
  die "missing venv_tuning. Run ./scripts/bootstrap_finetune_env.sh first."
fi

if [ -z "$SESSION_DIR" ]; then
  STAMP="$(date +%Y%m%d_%H%M%S)"
  SESSION_DIR="$ROOT_DIR/finetune/runs/${LABEL}_${STAMP}"
fi
mkdir -p "$SESSION_DIR"

canonicalize_session_scope

PREPARE_LOG="$SESSION_DIR/prepare.log"
WATCH_LOG="$SESSION_DIR/watch-loop.log"
PIPELINE_LOG="$SESSION_DIR/pipeline.log"
AUTO_REFRESH_LOG="$SESSION_DIR/dataset-refresh.log"
WATCH_PID_FILE="$SESSION_DIR/watch-loop.pid"
PIPELINE_PID_FILE="$SESSION_DIR/pipeline.pid"
META_FILE="$(tuning_party_meta_file "$SESSION_DIR")"
LATEST_FILE="$(tuning_party_latest_file "$LABEL")"

printf '%s\n' "$SESSION_DIR" >"$LATEST_FILE"
write_meta

if [ "$BACKGROUND" -eq 1 ] && [ "$INTERNAL_RUN" -eq 0 ]; then
  LAUNCHER_LOG="$SESSION_DIR/launcher.log"
  SESSION_CMD=(
    "$ROOT_DIR/scripts/start_tuning_party.sh"
    --run-session
    --session-dir "$SESSION_DIR"
    --label "$LABEL"
    --domain "$DOMAIN"
  )
  [ "$PREPARE" -eq 1 ] || SESSION_CMD+=(--skip-prepare)
  [ "$WATCH" -eq 1 ] || SESSION_CMD+=(--skip-watch)
  [ "$PIPELINE" -eq 1 ] || SESSION_CMD+=(--skip-pipeline)
  [ "$FOREGROUND_WATCH" -eq 1 ] && SESSION_CMD+=(--foreground-watch)
  [ "$VERBOSE" -eq 1 ] && SESSION_CMD+=(--verbose)
  SESSION_CMD+=(--watch-sleep "$WATCH_SLEEP_SECONDS")
  SESSION_CMD+=(--watch-max-sleep "$WATCH_MAX_SLEEP_SECONDS")
  SESSION_CMD+=(--watch-max-blocked "$WATCH_MAX_BLOCKED_STREAK")
  SESSION_CMD+=(--watch-max-failed "$WATCH_MAX_FAILED_STREAK")
  SESSION_CMD+=(--watch-max-ok "$WATCH_MAX_OK_CYCLES")
  SESSION_CMD+=(--watch-label "$WATCH_LABEL")
  SESSION_CMD+=(--monitor-interval "$MONITOR_INTERVAL")
  for arg in "${PIPELINE_ARGS[@]}"; do
    SESSION_CMD+=(--pipeline-arg "$arg")
  done

  nohup "${SESSION_CMD[@]}" >"$LAUNCHER_LOG" 2>&1 &
  SESSION_PID=$!
  printf '%s\n' "$SESSION_PID" >"$SESSION_DIR/session.pid"
  log "background session launched"
  log "session_dir=$SESSION_DIR"
  log "session_pid=$SESSION_PID"
  log "launcher_log=$LAUNCHER_LOG"
  exit 0
fi

log "session_dir=$SESSION_DIR"
log "llm_root=$MASCARADE_LLM_DIR"
info "Meta    : $META_FILE"

TOTAL_STEPS=0
[ "$AUTO_REFRESH_MISSING" -eq 1 ] && { [ "$PREPARE" -eq 1 ] || [ "$PIPELINE" -eq 1 ]; } && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$PREPARE" -eq 1 ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$WATCH" -eq 1 ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
[ "$PIPELINE" -eq 1 ] && TOTAL_STEPS=$((TOTAL_STEPS + 1))
CURRENT_STEP=0

if [ "$AUTO_REFRESH_MISSING" -eq 1 ] && { [ "$PREPARE" -eq 1 ] || [ "$PIPELINE" -eq 1 ]; }; then
  CURRENT_STEP=$((CURRENT_STEP + 1))
  print_step "$CURRENT_STEP" "$TOTAL_STEPS" "Refresh auto des dataset research manquants"
  run_auto_refresh_missing "$(resolve_refresh_domains_csv)"
  log "dataset_refresh_log=$AUTO_REFRESH_LOG"
  if [ "$VERBOSE" -eq 1 ] && [ -f "$AUTO_REFRESH_LOG" ]; then
    show_log_excerpt "Dataset refresh tail" "$AUTO_REFRESH_LOG"
  fi
fi

if [ "$PREPARE" -eq 1 ]; then
  CURRENT_STEP=$((CURRENT_STEP + 1))
  print_step "$CURRENT_STEP" "$TOTAL_STEPS" "Preparation du prochain lot utile"
  "$ROOT_DIR/scripts/next_finetune_lots.sh" --continue-on-error >"$PREPARE_LOG" 2>&1
  log "prepare_log=$PREPARE_LOG"
  if [ "$VERBOSE" -eq 1 ]; then
    show_log_excerpt "Prepare tail" "$PREPARE_LOG"
  fi
fi

if [ "$WATCH" -eq 1 ]; then
  CURRENT_STEP=$((CURRENT_STEP + 1))
  print_step "$CURRENT_STEP" "$TOTAL_STEPS" "Demarrage de la boucle watch"
  WATCH_CMD=(
    "$ROOT_DIR/scripts/auto_chain_next_lots_loop.sh"
    --label "$WATCH_LABEL"
    --iterations 1
    --sleep-seconds "$WATCH_SLEEP_SECONDS"
    --max-sleep-seconds "$WATCH_MAX_SLEEP_SECONDS"
    --max-blocked-streak "$WATCH_MAX_BLOCKED_STREAK"
    --max-failed-streak "$WATCH_MAX_FAILED_STREAK"
    --max-ok-cycles "$WATCH_MAX_OK_CYCLES"
    --max-cycles 0
    --pass-through-arg --continue-on-error
    --pass-through-arg --domain
    --pass-through-arg "$DOMAIN"
    --pass-through-arg --skip-watch-refresh
  )

  if [ "$FOREGROUND_WATCH" -eq 1 ] && [ "$PIPELINE" -eq 0 ]; then
    exec "${WATCH_CMD[@]}"
  fi

  if [ "$FOREGROUND_WATCH" -eq 1 ] && [ "$PIPELINE" -eq 1 ]; then
    die "--foreground-watch cannot be combined with pipeline execution"
  fi

  nohup "${WATCH_CMD[@]}" >"$WATCH_LOG" 2>&1 &
  WATCH_PID=$!
  printf '%s\n' "$WATCH_PID" >"$WATCH_PID_FILE"
  log "watch_pid=$WATCH_PID"
  log "watch_log=$WATCH_LOG"
  if [ "$VERBOSE" -eq 1 ]; then
    info "Watch command started in background"
    show_runtime_snapshot
  fi
fi

if [ "$PIPELINE" -eq 1 ]; then
  CURRENT_STEP=$((CURRENT_STEP + 1))
  print_step "$CURRENT_STEP" "$TOTAL_STEPS" "Pipeline complet SFT -> DPO"
  (
    cd "$ROOT_DIR/finetune"
    bash ./batch_full_pipeline.sh "${PIPELINE_ARGS[@]}"
  ) >"$PIPELINE_LOG" 2>&1 &
  PIPELINE_PID=$!
  printf '%s\n' "$PIPELINE_PID" >"$PIPELINE_PID_FILE"
  log "pipeline_pid=$PIPELINE_PID"
  log "pipeline_log=$PIPELINE_LOG"

  if [ "$VERBOSE" -eq 1 ]; then
    monitor_pipeline "$PIPELINE_PID" "$MONITOR_INTERVAL"
  else
    while tuning_party_pid_alive "$PIPELINE_PID"; do
      sleep "$MONITOR_INTERVAL"
    done
  fi

  wait "$PIPELINE_PID"
  section "Pipeline Complete"
  show_runtime_snapshot
  if [ "$VERBOSE" -eq 1 ]; then
    show_log_excerpt "Pipeline tail" "$PIPELINE_LOG"
  fi
  log "pipeline complete"
fi

log "done"
