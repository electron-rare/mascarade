#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CORE_DIR="$REPO_ROOT/core"

# shellcheck source=/Users/electron/mascarade/scripts/lib.sh
source "$REPO_ROOT/scripts/lib.sh"
setup_trap

CMD="run"
OPS_DIR="$REPO_ROOT/.ops/p2p-mesh-review"
ASSUME_YES=false
AUTO_PURGE=false
START_LOCAL_BRIDGE=false
RESEARCH_TIMEOUT=60
LOCAL_BRIDGE_PORT=4001

usage() {
    cat <<EOF
Usage: $SCRIPT_NAME <run|audit|research|purge> [options]

Commands:
  run               Execute mesh audit + ft-research dispatch and write a report
  audit             Execute mesh status + task distribution audit only
  research          Execute ft-research dispatch only
  purge             Delete review artifacts directory

Options:
  --ops-dir <path>          Artifact directory (default: $OPS_DIR)
  --start-local-bridge      Start the local bridge if it is not already listening
  --research-timeout <sec>  Timeout passed to ft-research dispatch (default: $RESEARCH_TIMEOUT)
  --purge                   Auto-purge artifacts after a successful run
  --yes                     Non-interactive approval for destructive steps
  -v, --verbose             Print extra execution details
  -h, --help                Show this help
EOF
}

parse_args_local() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            run|audit|research|purge)
                CMD="$1"
                shift
                ;;
            --ops-dir)
                [[ $# -ge 2 ]] || { err "--ops-dir requiert une valeur"; exit 2; }
                OPS_DIR="$2"
                shift 2
                ;;
            --start-local-bridge)
                START_LOCAL_BRIDGE=true
                shift
                ;;
            --research-timeout)
                [[ $# -ge 2 ]] || { err "--research-timeout requiert une valeur"; exit 2; }
                RESEARCH_TIMEOUT="$2"
                shift 2
                ;;
            --purge)
                AUTO_PURGE=true
                shift
                ;;
            --yes)
                ASSUME_YES=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
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
}

run_capture() {
    local name="$1"
    shift
    local logfile="$OPS_DIR/${name}.log"
    dbg "run_capture[$name]: $*"
    set +e
    "$@" >"$logfile" 2>&1
    local rc=$?
    set -e
    printf '%s\n' "$rc" >"$OPS_DIR/${name}.rc"
    return "$rc"
}

read_rc() {
    local name="$1"
    if [[ -f "$OPS_DIR/${name}.rc" ]]; then
        cat "$OPS_DIR/${name}.rc"
    else
        echo "999"
    fi
}

extract_bootstrap_peer_id() {
    ssh -o ConnectTimeout=5 "root@192.168.0.119" "head -1 /tmp/p2p_node.log" 2>/dev/null | \
        python3 -c 'import json,sys; print(json.loads(sys.stdin.read().strip()).get("peer_id",""))'
}

local_mesh_pid() {
    local port="${1:-$LOCAL_BRIDGE_PORT}"
    local pid=""
    pid="$(lsof -ti:"$port" 2>/dev/null | head -1 || true)"
    if [[ -n "$pid" ]] && ps -p "$pid" -o command= | grep -Eq "node_start_bridge.py|task_handler_worker.py"; then
        echo "$pid"
    fi
}

select_local_bridge_port() {
    if [[ -n "$(local_mesh_pid 4001 || true)" ]]; then
        LOCAL_BRIDGE_PORT=4001
        return 0
    fi
    if lsof -ti:4001 >/dev/null 2>&1; then
        warn "Port 4001 is occupied by a non-bridge process; using fallback port 4101 for the local bridge."
        LOCAL_BRIDGE_PORT=4101
        return 0
    fi
    LOCAL_BRIDGE_PORT=4001
}

ensure_local_bridge() {
    select_local_bridge_port

    if [[ -n "$(local_mesh_pid "$LOCAL_BRIDGE_PORT" || true)" ]]; then
        ok "Local fine-tune node already listening on :$LOCAL_BRIDGE_PORT"
        return 0
    fi

    if [[ "$START_LOCAL_BRIDGE" != true ]]; then
        warn "Local fine-tune node not listening on :$LOCAL_BRIDGE_PORT"
        warn "Re-run with --start-local-bridge to spawn it locally."
        return 1
    fi

    local bootstrap_peer_id=""
    bootstrap_peer_id="$(extract_bootstrap_peer_id)"
    [[ -n "$bootstrap_peer_id" ]] || {
        err "Impossible de lire le peer_id bootstrap depuis la VM."
        return 1
    }

    local worker_py="$CORE_DIR/.venv/bin/python"
    [[ -x "$worker_py" ]] || worker_py="python3"

    section "Local Fine-tune Node"
    info "Starting task_handler_worker.py on :$LOCAL_BRIDGE_PORT"
    (
        cd "$CORE_DIR"
        P2P_BOOTSTRAP_ID="$bootstrap_peer_id" \
        P2P_BOOTSTRAP_PORT="4001" \
        P2P_LISTEN_PORT="$LOCAL_BRIDGE_PORT" \
        P2P_LABEL="GrosMac Research" \
        P2P_CAPABILITIES="ft-research,ft-dataset,ft-teacher,ft-archive" \
        nohup "$worker_py" scripts/p2p/task_handler_worker.py </dev/null >/tmp/p2p_bridge.log 2>&1 &
    )
    sleep 4

    if [[ -n "$(local_mesh_pid "$LOCAL_BRIDGE_PORT" || true)" ]]; then
        ok "Local fine-tune node started"
        return 0
    fi

    err "Local fine-tune node failed to start"
    sed -n '1,40p' /tmp/p2p_bridge.log >&2 || true
    return 1
}

render_report() {
    local report="$OPS_DIR/report.md"
    local status_rc test_rc research_rc
    status_rc="$(read_rc status)"
    test_rc="$(read_rc task_test)"
    research_rc="$(read_rc research)"

    {
        echo "# P2P Mesh Review"
        echo
        echo "- date_utc: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        echo "- repo_root: $REPO_ROOT"
        echo "- local_bridge_port: $LOCAL_BRIDGE_PORT"
        echo "- start_local_bridge: $START_LOCAL_BRIDGE"
        echo
        echo "## Exit Codes"
        echo
        echo "| Step | rc |"
        echo "| --- | --- |"
        echo "| status | $status_rc |"
        echo "| task_test | $test_rc |"
        echo "| research | $research_rc |"
        echo
        for name in status task_test research; do
            local logfile="$OPS_DIR/${name}.log"
            if [[ -f "$logfile" ]]; then
                echo "## ${name}"
                echo
                echo '```text'
                sed -n '1,160p' "$logfile"
                echo '```'
                echo
            fi
        done
    } >"$report"
    ok "Report written: $report"
}

run_audit() {
    mkdir -p "$OPS_DIR"
    select_local_bridge_port
    section "P2P Mesh Audit"
    info "Ops dir: $OPS_DIR"
    info "Local bridge port candidate: $LOCAL_BRIDGE_PORT"
    run_capture status env LOCAL_BRIDGE_PORT="$LOCAL_BRIDGE_PORT" bash "$CORE_DIR/scripts/p2p/run_all.sh" status || true
    run_capture task_test env LOCAL_BRIDGE_PORT="$LOCAL_BRIDGE_PORT" bash "$CORE_DIR/scripts/p2p/run_all.sh" test || true
    printf '%s\n' "999" >"$OPS_DIR/research.rc"
    render_report
}

run_research() {
    mkdir -p "$OPS_DIR"
    ensure_local_bridge
    section "ft-research"
    info "Dispatch timeout: ${RESEARCH_TIMEOUT}s"
    info "Local bridge port: $LOCAL_BRIDGE_PORT"
    run_capture research env LOCAL_BRIDGE_PORT="$LOCAL_BRIDGE_PORT" RESEARCH_TIMEOUT_SECONDS="$RESEARCH_TIMEOUT" bash "$CORE_DIR/scripts/p2p/run_all.sh" research || true
    [[ -f "$OPS_DIR/status.rc" ]] || printf '%s\n' "999" >"$OPS_DIR/status.rc"
    [[ -f "$OPS_DIR/task_test.rc" ]] || printf '%s\n' "999" >"$OPS_DIR/task_test.rc"
    render_report
}

purge_ops() {
    if [[ ! -d "$OPS_DIR" ]]; then
        warn "Nothing to purge: $OPS_DIR"
        return 0
    fi
    if [[ "$ASSUME_YES" != true ]]; then
        confirm "Delete audit artifacts at $OPS_DIR ?" || {
            warn "Purge cancelled."
            return 1
        }
    fi
    rm -rf "$OPS_DIR"
    ok "Purged: $OPS_DIR"
}

main() {
    parse_args_local "$@"

    case "$CMD" in
        audit)
            run_audit
            ;;
        research)
            run_research
            ;;
        purge)
            purge_ops
            ;;
        run)
            run_audit
            run_research
            if [[ "$AUTO_PURGE" == true ]]; then
                purge_ops || true
            fi
            ;;
        *)
            err "Commande non supportee: $CMD"
            exit 2
            ;;
    esac
}

main "$@"
