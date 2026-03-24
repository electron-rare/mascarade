#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/Users/electron/Documents/Projets/mascarade/scripts/lib.sh
source "$SCRIPT_DIR/../lib.sh"

PLAN_PATH="$REPO_DIR/docs/plan/2026-03-24-sota-mascarade/active_execution_plan.md"
LOG_DIR="$REPO_DIR/tmp"
LOG_FILE="$LOG_DIR/next_lot_control.log"
ACTION="status"
KEEP_LOG=false

usage() {
    cat <<'EOF'
Usage: bash scripts/tui/next_lot_control.sh [status|run|show-log|cleanup-log] [--keep-log]

Pilotage TUI minimal des prochains lots actifs Mascarade.

Actions:
  status       Afficher le plan actif et les artefacts clés
  run          Exécuter le lot d'inspection local et écrire un log temporaire
  show-log     Afficher le log temporaire s'il existe
  cleanup-log  Supprimer le log temporaire
EOF
}

log_event() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    mkdir -p "$LOG_DIR"
    printf '[%s] %s\n' "$ts" "$*" >> "$LOG_FILE"
}

print_status() {
    section "Next Lot Control"
    info "Plan actif: $PLAN_PATH"
    info "Log temporaire: $LOG_FILE"
    echo
    printf '  %-34s %s\n' "Plan actif" "$( [[ -f "$PLAN_PATH" ]] && echo oui || echo non )"
    printf '  %-34s %s\n' "Test circuit breaker present" "$( rg -q 'half_open_budget_is_consumed' "$REPO_DIR/core/tests/test_health_integration.py" && echo oui || echo non )"
    printf '  %-34s %s\n' "Plan execution anchor present" "$( [[ -f "$REPO_DIR/docs/plan/2026-03-24-sota-mascarade/active_execution_plan.md" ]] && echo oui || echo non )"
}

run_inspection() {
    section "Execution Next Lots"
    mkdir -p "$LOG_DIR"
    : > "$LOG_FILE"

    log_event "start next lot inspection"
    log_event "plan_exists=$( [[ -f "$PLAN_PATH" ]] && echo yes || echo no )"
    log_event "changed_docs=$(git -C "$REPO_DIR" status --short docs scripts core/tests core/mascarade/router 2>/dev/null | wc -l | tr -d ' ')"
    log_event "half_open_test=$(rg -n 'half_open_budget_is_consumed' "$REPO_DIR/core/tests/test_health_integration.py" | tr '\n' ' ' || true)"
    log_event "circuit_breaker_budget=$(rg -n 'half_open_calls \+= 1' "$REPO_DIR/core/mascarade/router/circuit_breaker.py" | tr '\n' ' ' || true)"

    ok "Inspection terminee"
    info "Log ecrit: $LOG_FILE"
    echo
    tail -n 10 "$LOG_FILE" | sed 's/^/  /'

    if [[ "$KEEP_LOG" != true ]]; then
        info "Le log peut etre supprime avec: bash scripts/tui/next_lot_control.sh cleanup-log"
    fi
}

show_log() {
    section "Log Temporaire"
    if [[ ! -f "$LOG_FILE" ]]; then
        warn "Aucun log temporaire present"
        return 0
    fi
    sed 's/^/  /' "$LOG_FILE"
}

cleanup_log() {
    section "Cleanup Log"
    if [[ -f "$LOG_FILE" ]]; then
        rm -f "$LOG_FILE"
        ok "Log temporaire supprime"
    else
        warn "Aucun log a supprimer"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        status|run|show-log|cleanup-log)
            ACTION="$1"
            shift
            ;;
        --keep-log)
            KEEP_LOG=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "Argument inconnu: $1"
            usage
            exit 2
            ;;
    esac
done

case "$ACTION" in
    status) print_status ;;
    run) run_inspection ;;
    show-log) show_log ;;
    cleanup-log) cleanup_log ;;
esac
