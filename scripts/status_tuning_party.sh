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
Usage: ./scripts/status_tuning_party.sh [options]

Affiche l'etat de la session tuning party courante.

Options:
  --label NAME         Label de session (default: tuning-party)
  --session-dir PATH   Session explicite
  --verbose            Affiche un extrait des logs
  -h, --help           Affiche l'aide
EOF
}

die() {
  echo "status-tuning-party: $*" >&2
  exit 1
}

LABEL="tuning-party"
SESSION_DIR=""
VERBOSE=0

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

SESSION_DIR="$(tuning_party_resolve_session_dir "$LABEL" "$SESSION_DIR" || true)"
[[ -n "$SESSION_DIR" ]] || die "no session found for label '$LABEL'"
tuning_party_load_meta "$SESSION_DIR" || die "missing session metadata in $SESSION_DIR"

WATCH_PID=""
PIPELINE_PID=""
CPU_STUDENTS_PID=""
REVIEWER_PID=""
DOCTOR_PID=""
[[ -f "$WATCH_PID_FILE" ]] && WATCH_PID="$(head -n 1 "$WATCH_PID_FILE" 2>/dev/null || true)"
[[ -f "$PIPELINE_PID_FILE" ]] && PIPELINE_PID="$(head -n 1 "$PIPELINE_PID_FILE" 2>/dev/null || true)"
[[ -n "${CPU_STUDENTS_PID_FILE:-}" && -f "$CPU_STUDENTS_PID_FILE" ]] && CPU_STUDENTS_PID="$(head -n 1 "$CPU_STUDENTS_PID_FILE" 2>/dev/null || true)"
[[ -n "${REVIEWER_PID_FILE:-}" && -f "$REVIEWER_PID_FILE" ]] && REVIEWER_PID="$(head -n 1 "$REVIEWER_PID_FILE" 2>/dev/null || true)"
[[ -n "${DOCTOR_PID_FILE:-}" && -f "$DOCTOR_PID_FILE" ]] && DOCTOR_PID="$(head -n 1 "$DOCTOR_PID_FILE" 2>/dev/null || true)"

IFS='|' read -r PIPELINE_PHASE PIPELINE_CURRENT PIPELINE_TOTAL < <(tuning_party_pipeline_phase "$PIPELINE_LOG")
WATCH_STATE="$(tuning_party_watch_state "$WATCH_LOG")"

printf 'session=%s\n' "$SESSION_DIR"
printf 'prepare_log=%s\n' "$PREPARE_LOG"
printf 'watch_log=%s\n' "$WATCH_LOG"
printf 'pipeline_log=%s\n' "$PIPELINE_LOG"
printf 'watch=%s pid=%s alive=%s\n' \
  "$WATCH_STATE" \
  "${WATCH_PID:-n/a}" \
  "$([[ -n "$WATCH_PID" ]] && tuning_party_pid_alive "$WATCH_PID" && echo yes || echo no)"
printf 'pipeline=%s %s pid=%s alive=%s\n' \
  "$PIPELINE_PHASE" \
  "$(tuning_party_bar "$PIPELINE_CURRENT" "$PIPELINE_TOTAL" 18)" \
  "${PIPELINE_PID:-n/a}" \
  "$([[ -n "$PIPELINE_PID" ]] && tuning_party_pid_alive "$PIPELINE_PID" && echo yes || echo no)"
printf 'cpu_students=%s preset=%s threads=%s domains=%s pid=%s alive=%s\n' \
  "$([[ "${CPU_STUDENTS_ENABLED:-0}" -eq 1 ]] && echo enabled || echo disabled)" \
  "${CPU_PRESET:-n/a}" \
  "${CPU_THREADS_PER_STUDENT:-n/a}" \
  "${CPU_STUDENT_DOMAINS:-n/a}" \
  "${CPU_STUDENTS_PID:-n/a}" \
  "$([[ -n "$CPU_STUDENTS_PID" ]] && tuning_party_pid_alive "$CPU_STUDENTS_PID" && echo yes || echo no)"
printf 'reviewer=%s pid=%s alive=%s\n' \
  "$([[ "${REVIEWER_ENABLED:-0}" -eq 1 ]] && echo enabled || echo disabled)" \
  "${REVIEWER_PID:-n/a}" \
  "$([[ -n "$REVIEWER_PID" ]] && tuning_party_pid_alive "$REVIEWER_PID" && echo yes || echo no)"
printf 'doctor=%s threads=%s pid=%s alive=%s\n' \
  "$([[ "${DOCTOR_ENABLED:-0}" -eq 1 ]] && echo enabled || echo disabled)" \
  "${DOCTOR_THREADS:-n/a}" \
  "${DOCTOR_PID:-n/a}" \
  "$([[ -n "$DOCTOR_PID" ]] && tuning_party_pid_alive "$DOCTOR_PID" && echo yes || echo no)"
printf '%s\n' "$(tuning_party_gpu_summary)"
if [[ -n "${PIPELINE_DOMAINS:-}" && "${PIPELINE_DOMAINS:-}" != "${DOMAIN:-}" && "${PIPELINE_DOMAINS:-}" != "unknown" ]]; then
  tuning_party_format_dataset_research_status "$(tuning_party_dataset_research_summary "$PIPELINE_DOMAINS")"
elif [[ -n "${DOMAIN:-}" ]]; then
  tuning_party_format_dataset_research_status "$(tuning_party_dataset_research_status "$DOMAIN")"
fi

if [ "$VERBOSE" -eq 1 ]; then
  if [ -f "$WATCH_LOG" ]; then
    printf '\nwatch_tail:\n'
    tail -n 10 "$WATCH_LOG"
  fi
  if [ -f "$PIPELINE_LOG" ]; then
    printf '\npipeline_tail:\n'
    tail -n 10 "$PIPELINE_LOG"
  fi
  if [ -n "${CPU_STUDENTS_LOG:-}" ] && [ -f "$CPU_STUDENTS_LOG" ]; then
    printf '\ncpu_students_tail:\n'
    tail -n 10 "$CPU_STUDENTS_LOG"
  fi
  if [ -n "${REVIEWER_LOG:-}" ] && [ -f "$REVIEWER_LOG" ]; then
    printf '\nreviewer_tail:\n'
    tail -n 10 "$REVIEWER_LOG"
  fi
  if [ -n "${DOCTOR_LOG:-}" ] && [ -f "$DOCTOR_LOG" ]; then
    printf '\ndoctor_tail:\n'
    tail -n 10 "$DOCTOR_LOG"
  fi
fi
