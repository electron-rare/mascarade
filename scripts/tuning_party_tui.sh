#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/lib.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/tuning_party_common.sh"

LABEL="tuning-party"
REFRESH_SECONDS=5

usage() {
  cat <<'EOF'
Usage: ./scripts/tuning_party_tui.sh [options]

Interface TUI interactive pour piloter la tuning party.

Options:
  --label NAME       Label de session (default: tuning-party)
  --interval N       Refresh dashboard en secondes (default: 5)
  --dashboard        Ouvre directement le dashboard live
  -h, --help         Affiche l'aide
EOF
}

die() {
  echo "tuning-party-tui: $*" >&2
  exit 1
}

dashboard_width() {
  local cols="${COLUMNS:-}"
  if [[ -z "$cols" ]] && command -v tput >/dev/null 2>&1; then
    cols="$(tput cols 2>/dev/null || true)"
  fi
  [[ "$cols" =~ ^[0-9]+$ ]] || cols=120
  printf '%s\n' "$cols"
}

dashboard_hr() {
  local width="$1"
  printf '  '
  printf '%*s\n' "$width" '' | tr ' ' '-'
}

fit_text() {
  local text="$1"
  local width="$2"
  if (( ${#text} > width )); then
    printf '%s\n' "${text:0:width-3}..."
  else
    printf '%-*s\n' "$width" "$text"
  fi
}

highlight_line() {
  local line="$1"
  if [[ "$line" =~ (ERROR|Error|error|FAILED|failed|Traceback|OOM|CUDA\ OOM) ]]; then
    printf '    %b%s%b\n' "$RED" "$line" "$NC"
  elif [[ "$line" =~ (WARN|Warning|warning|blocked|unavailable) ]]; then
    printf '    %b%s%b\n' "$YELLOW" "$line" "$NC"
  else
    printf '    %s\n' "$line"
  fi
}

render_log_panel() {
  local title="$1"
  local file_path="$2"
  local lines="${3:-6}"
  local width="$4"
  echo -e "  ${BOLD}${title}${NC}"
  if [[ ! -f "$file_path" ]]; then
    echo -e "    ${DIM}log absent${NC}"
    return 0
  fi
  while IFS= read -r line; do
    if (( ${#line} > width )); then
      line="${line:0:width-3}..."
    fi
    highlight_line "$line"
  done < <(tail -n "$lines" "$file_path")
}

render_dataset_research_details() {
  local raw="$1"
  local width="$2"
  local details=""
  if [[ "$raw" == *" details="* ]]; then
    details="${raw#* details=}"
  fi
  echo -e "  ${BOLD}Dataset Research${NC}"
  if [[ -z "$details" ]]; then
    echo -e "    ${DIM}no extra dataset research detail${NC}"
    return 0
  fi
  local item
  IFS=',' read -r -a items <<< "$details"
  for item in "${items[@]}"; do
    if (( ${#item} > width )); then
      item="${item:0:width-3}..."
    fi
    highlight_line "$item"
  done
}

render_dataset_probe_details() {
  local domains_csv="$1"
  local width="$2"
  echo -e "  ${BOLD}Web Probes${NC}"
  local line found=0
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    found=1
    if (( ${#line} > width )); then
      line="${line:0:width-3}..."
    fi
    highlight_line "$line"
  done < <(tuning_party_dataset_probe_details "$domains_csv")
  if [[ "$found" -eq 0 ]]; then
    echo -e "    ${DIM}no probe detail${NC}"
  fi
}

status_badge() {
  local label="$1"
  local value="$2"
  printf '%s:%s' "$label" "$value"
}

render_summary_row() {
  local width="$1"
  local left="$2"
  local center="$3"
  local right="$4"
  local col=$(( (width - 6) / 3 ))
  local left_fit center_fit right_fit
  left_fit="$(fit_text "$left" "$col")"
  center_fit="$(fit_text "$center" "$col")"
  right_fit="$(fit_text "$right" "$col")"
  printf '  %s | %s | %s' "${left_fit%$'\n'}" "${center_fit%$'\n'}" "${right_fit%$'\n'}"
  printf '\n'
}

render_dashboard() {
  local session_dir="$1"
  local width log_width
  width="$(dashboard_width)"
  log_width=$(( width - 8 ))

  if ! tuning_party_load_meta "$session_dir"; then
    clear
    banner
    section "Dashboard"
    warn "Metadata absente pour $session_dir"
    return 0
  fi

  local watch_pid="" pipeline_pid=""
  [[ -f "$WATCH_PID_FILE" ]] && watch_pid="$(head -n 1 "$WATCH_PID_FILE" 2>/dev/null || true)"
  [[ -f "$PIPELINE_PID_FILE" ]] && pipeline_pid="$(head -n 1 "$PIPELINE_PID_FILE" 2>/dev/null || true)"

  local pipeline_phase pipeline_current pipeline_total
  IFS='|' read -r pipeline_phase pipeline_current pipeline_total < <(tuning_party_pipeline_phase "$PIPELINE_LOG")
  local watch_state gpu_state dataset_state domain_label research_file_label
  watch_state="$(tuning_party_watch_state "$WATCH_LOG")"
  gpu_state="$(tuning_party_gpu_summary)"
  if [[ -n "${PIPELINE_DOMAINS:-}" && "${PIPELINE_DOMAINS:-}" != "${DOMAIN:-}" && "${PIPELINE_DOMAINS:-}" != "unknown" ]]; then
    dataset_state="$(tuning_party_dataset_research_summary "${PIPELINE_DOMAINS:-}")"
    domain_label="Domains: ${PIPELINE_DOMAINS:-n/a}"
    research_file_label="Research: aggregate"
  else
    dataset_state="$(tuning_party_dataset_research_status "${DOMAIN:-}")"
    domain_label="Domain: ${DOMAIN:-n/a}"
    research_file_label="Research file: ${DOMAIN:-n/a}_refresh.json"
  fi
  local dataset_state_fmt
  dataset_state_fmt="$(tuning_party_format_dataset_research_status "$dataset_state")"
  local watch_alive="no" pipeline_alive="no"
  [[ -n "$watch_pid" ]] && tuning_party_pid_alive "$watch_pid" && watch_alive="yes"
  [[ -n "$pipeline_pid" ]] && tuning_party_pid_alive "$pipeline_pid" && pipeline_alive="yes"

  clear
  banner
  section "Live Dashboard"
  dashboard_hr "$(( width - 2 ))"
  render_summary_row "$(( width - 2 ))" \
    "Session: $(basename "$session_dir")" \
    "Refresh: ${REFRESH_SECONDS}s" \
    "$gpu_state"
  render_summary_row "$(( width - 2 ))" \
    "$(status_badge "Watch" "$watch_state") pid=${watch_pid:-n/a} alive=${watch_alive}" \
    "$(status_badge "Pipeline" "$pipeline_phase") $(tuning_party_bar "$pipeline_current" "$pipeline_total" 16)" \
    "pipeline pid=${pipeline_pid:-n/a} alive=${pipeline_alive}"
  render_summary_row "$(( width - 2 ))" \
    "${dataset_state_fmt%$'\n'}" \
    "$domain_label" \
    "$research_file_label"
  dashboard_hr "$(( width - 2 ))"
  echo ""
  if [[ "$dataset_state" == *"research=partial"* || "$dataset_state" == *"research=blocked"* || "$dataset_state" == *"research=missing"* ]]; then
    render_dataset_research_details "$dataset_state" "$log_width"
    echo ""
    render_dataset_probe_details "${PIPELINE_DOMAINS:-${DOMAIN:-}}" "$log_width"
    echo ""
  fi
  echo ""
  render_log_panel "Preparation" "$PREPARE_LOG" 4 "$log_width"
  echo ""
  render_log_panel "Watch Loop" "$WATCH_LOG" 6 "$log_width"
  echo ""
  render_log_panel "Pipeline" "$PIPELINE_LOG" 10 "$log_width"
  echo ""
  echo -e "  ${DIM}Touches: q quitter | r refresh | m menu${NC}"
}

live_dashboard() {
  local session_dir
  session_dir="$(tuning_party_resolve_session_dir "$LABEL" "" || true)"
  if [[ -z "$session_dir" ]]; then
    section "Live Dashboard"
    warn "Aucune session active"
    return 0
  fi

  while true; do
    render_dashboard "$session_dir"
    local key=""
    if read -r -s -n 1 -t "$REFRESH_SECONDS" key; then
      case "$key" in
        q) return 0 ;;
        m) return 0 ;;
        r) continue ;;
      esac
    fi
  done
}

show_status() {
  section "Tuning Party Status"
  "$ROOT_DIR/scripts/status_tuning_party.sh" --label "$LABEL" --verbose || warn "Aucune session active"
}

launch_session() {
  local mode_flag="$1"
  local verbose_flag="$2"
  section "Start Tuning Party"
  info "Label: $LABEL"
  info "Mode: ${mode_flag:---full}"
  "$ROOT_DIR/scripts/start_tuning_party.sh" --background --label "$LABEL" $mode_flag $verbose_flag
  live_dashboard
}

start_session() {
  menu_select "Mode de lancement ?" \
    "Session complete" \
    "Preparation uniquement" \
    "Watch uniquement" \
    "Pipeline uniquement"

  local mode_flag=""
  case "$MENU_RESULT" in
    1) mode_flag="--prepare-only" ;;
    2) mode_flag="--watch-only" ;;
    3) mode_flag="--pipeline-only" ;;
  esac

  local verbose_flag=""
  if confirm "Activer le monitoring verbeux ?"; then
    verbose_flag="--verbose"
  fi

  launch_session "$mode_flag" "$verbose_flag"
}

stop_session() {
  if ! confirm "Arreter la session tuning party courante ?"; then
    return 0
  fi
  section "Stop Tuning Party"
  "$ROOT_DIR/scripts/stop_tuning_party.sh" --label "$LABEL" || warn "Aucune session active"
}

stop_all_sessions() {
  if ! confirm "Arreter toutes les sessions tuning party et les vieux runs batch connus ?"; then
    return 0
  fi
  section "Stop All Tuning Tasks"
  "$ROOT_DIR/scripts/stop_tuning_party.sh" --all --force || warn "Aucune tache active detectee"
}

restart_clean_session() {
  local mode_flag=""
  local verbose_flag=""

  if ! confirm "Redemarrer proprement la tuning party ?"; then
    return 0
  fi

  menu_select "Mode apres restart clean ?" \
    "Session complete" \
    "Preparation uniquement" \
    "Watch uniquement" \
    "Pipeline uniquement"

  case "$MENU_RESULT" in
    1) mode_flag="--prepare-only" ;;
    2) mode_flag="--watch-only" ;;
    3) mode_flag="--pipeline-only" ;;
  esac

  if confirm "Activer le monitoring verbeux apres relance ?"; then
    verbose_flag="--verbose"
  fi

  section "Restart Clean"
  "$ROOT_DIR/scripts/stop_tuning_party.sh" --all --force || warn "Aucune tache active detectee"
  info "Etat GPU: $(tuning_party_gpu_summary)"
  launch_session "$mode_flag" "$verbose_flag"
}

tail_logs() {
  local session_dir
  session_dir="$(tuning_party_resolve_session_dir "$LABEL" "" || true)"
  if [[ -z "$session_dir" ]]; then
    warn "Aucune session a afficher"
    return 0
  fi

  menu_select "Quel log afficher ?" \
    "Pipeline" \
    "Watch loop" \
    "Preparation"

  local log_file=""
  case "$MENU_RESULT" in
    0) log_file="$session_dir/pipeline.log" ;;
    1) log_file="$session_dir/watch-loop.log" ;;
    2) log_file="$session_dir/prepare.log" ;;
  esac

  [[ -f "$log_file" ]] || {
    warn "Log absent: $log_file"
    return 0
  }

  section "Tail Log"
  info "$log_file"
  tail -n 40 "$log_file"
}

show_workflow() {
  section "Workflow"
  info "Sources locales/web -> build domaine -> normalisation -> quality gate -> dedupe -> package HF"
  info "-> consommation par distill/train -> selection modele -> lot utile -> benchmark candidat"
  info "-> pipeline SFT/DPO -> promotion"
}

main() {
  local direct_dashboard=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --label)
        [[ $# -ge 2 ]] || die "--label requires a value"
        LABEL="$2"
        shift 2
        ;;
      --interval)
        [[ $# -ge 2 ]] || die "--interval requires a value"
        [[ "$2" =~ ^[0-9]+$ ]] || die "--interval must be a non-negative integer"
        REFRESH_SECONDS="$2"
        shift 2
        ;;
      --dashboard)
        direct_dashboard=1
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
  if [[ ! -t 0 || ! -t 1 ]]; then
    echo "tuning-party-tui: interactive TTY required" >&2
    exit 1
  fi
  activate_tui
  banner

  if [[ "$direct_dashboard" -eq 1 ]]; then
    live_dashboard
  fi

  while true; do
    menu_select "Tuning Party TUI" \
      "Start session" \
      "Restart clean" \
      "Live dashboard" \
      "Status current" \
      "Stop current" \
      "Stop all tasks" \
      "Tail latest logs" \
      "Show workflow" \
      "Exit"

    case "$MENU_RESULT" in
      0) start_session ;;
      1) restart_clean_session ;;
      2) live_dashboard ;;
      3) show_status ;;
      4) stop_session ;;
      5) stop_all_sessions ;;
      6) tail_logs ;;
      7) show_workflow ;;
      8) exit 0 ;;
    esac
  done
}

main "$@"
