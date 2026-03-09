#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/tuning_party_common.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/stop_tuning_party.sh [options]

Arrete la session tuning party courante.

Options:
  --label NAME         Label de session (default: tuning-party)
  --session-dir PATH   Session explicite
  --all                Arrete toutes les sessions tuning party et les vieux runs batch connus
  --force              Termine avec KILL si TERM ne suffit pas
  -h, --help           Affiche l'aide
EOF
}

die() {
  echo "stop-tuning-party: $*" >&2
  exit 1
}

stop_pid() {
  local pid="$1"
  local force="$2"
  if ! tuning_party_pid_alive "$pid"; then
    return 0
  fi
  pkill -TERM -P "$pid" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
  sleep 2
  if [ "$force" -eq 1 ] && tuning_party_pid_alive "$pid"; then
    pkill -KILL -P "$pid" 2>/dev/null || true
    kill -9 "$pid" 2>/dev/null || true
  fi
}

stop_session_dir() {
  local session_dir="$1"
  local force="$2"
  local watch_pid_file pipeline_pid_file cpu_students_pid_file reviewer_pid_file doctor_pid_file
  local watch_pid="" pipeline_pid="" cpu_students_pid="" reviewer_pid="" doctor_pid=""

  if ! tuning_party_load_meta "$session_dir"; then
    printf 'session=%s skipped (missing metadata)\n' "$session_dir"
    return 0
  fi

  watch_pid_file="${WATCH_PID_FILE:-}"
  pipeline_pid_file="${PIPELINE_PID_FILE:-}"
  cpu_students_pid_file="${CPU_STUDENTS_PID_FILE:-}"
  reviewer_pid_file="${REVIEWER_PID_FILE:-}"
  doctor_pid_file="${DOCTOR_PID_FILE:-}"
  [[ -n "$watch_pid_file" && -f "$watch_pid_file" ]] && watch_pid="$(head -n 1 "$watch_pid_file" 2>/dev/null || true)"
  [[ -n "$pipeline_pid_file" && -f "$pipeline_pid_file" ]] && pipeline_pid="$(head -n 1 "$pipeline_pid_file" 2>/dev/null || true)"
  [[ -n "$cpu_students_pid_file" && -f "$cpu_students_pid_file" ]] && cpu_students_pid="$(head -n 1 "$cpu_students_pid_file" 2>/dev/null || true)"
  [[ -n "$reviewer_pid_file" && -f "$reviewer_pid_file" ]] && reviewer_pid="$(head -n 1 "$reviewer_pid_file" 2>/dev/null || true)"
  [[ -n "$doctor_pid_file" && -f "$doctor_pid_file" ]] && doctor_pid="$(head -n 1 "$doctor_pid_file" 2>/dev/null || true)"

  if [[ -n "$watch_pid" ]]; then
    stop_pid "$watch_pid" "$force"
    printf 'watch pid=%s alive=%s\n' "$watch_pid" "$([[ -n "$watch_pid" ]] && tuning_party_pid_alive "$watch_pid" && echo yes || echo no)"
  fi

  if [[ -n "$pipeline_pid" ]]; then
    stop_pid "$pipeline_pid" "$force"
    printf 'pipeline pid=%s alive=%s\n' "$pipeline_pid" "$([[ -n "$pipeline_pid" ]] && tuning_party_pid_alive "$pipeline_pid" && echo yes || echo no)"
  fi

  if [[ -n "$cpu_students_pid" ]]; then
    stop_pid "$cpu_students_pid" "$force"
    printf 'cpu_students pid=%s alive=%s\n' "$cpu_students_pid" "$([[ -n "$cpu_students_pid" ]] && tuning_party_pid_alive "$cpu_students_pid" && echo yes || echo no)"
  fi

  if [[ -n "$reviewer_pid" ]]; then
    stop_pid "$reviewer_pid" "$force"
    printf 'reviewer pid=%s alive=%s\n' "$reviewer_pid" "$([[ -n "$reviewer_pid" ]] && tuning_party_pid_alive "$reviewer_pid" && echo yes || echo no)"
  fi

  if [[ -n "$doctor_pid" ]]; then
    stop_pid "$doctor_pid" "$force"
    printf 'doctor pid=%s alive=%s\n' "$doctor_pid" "$([[ -n "$doctor_pid" ]] && tuning_party_pid_alive "$doctor_pid" && echo yes || echo no)"
  fi

  printf 'session=%s stopped\n' "$session_dir"
}

stop_known_legacy_batches() {
  local force="$1"
  local pids=()
  while IFS= read -r pid; do
    [[ -n "$pid" ]] && pids+=("$pid")
  done < <(
    ps -eo pid,cmd 2>/dev/null \
      | grep -E '(batch_phase_a\.sh|batch_full_pipeline\.sh|python .*run_local\.py|python .*train_local\.py|train_parallel\.sh|reviewer_consolidator\.sh|doctor_worker\.sh)' \
      | grep -v 'grep -E' \
      | awk '{print $1}'
  )

  if [[ "${#pids[@]}" -eq 0 ]]; then
    printf 'legacy_runs=none\n'
    return 0
  fi

  printf 'legacy_runs=%s\n' "${pids[*]}"
  for pid in "${pids[@]}"; do
    stop_pid "$pid" "$force"
  done
}

LABEL="tuning-party"
SESSION_DIR=""
FORCE=0
STOP_ALL=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --label)
      [ "$#" -ge 2 ] || die "--label requires a value"
      LABEL="$2"
      shift 2
      ;;
    --session-dir)
      [ "$#" -ge 2 ] || die "--session-dir requires a value"
      SESSION_DIR="$2"
      shift 2
      ;;
    --all)
      STOP_ALL=1
      shift
      ;;
    --force)
      FORCE=1
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

if [[ "$STOP_ALL" -eq 1 ]]; then
  found_any=0
  while IFS= read -r session_path; do
    [[ -d "$session_path" ]] || continue
    found_any=1
    stop_session_dir "$session_path" "$FORCE"
  done < <(find "$ROOT_DIR/finetune/runs" -maxdepth 1 -type d -name 'tuning-party_*' 2>/dev/null | sort)
  stop_known_legacy_batches "$FORCE"
  if [[ "$found_any" -eq 0 ]]; then
    printf 'sessions=none\n'
  fi
  exit 0
fi

SESSION_DIR="$(tuning_party_resolve_session_dir "$LABEL" "$SESSION_DIR" || true)"
[[ -n "$SESSION_DIR" ]] || die "no session found for label '$LABEL'"
stop_session_dir "$SESSION_DIR" "$FORCE"
