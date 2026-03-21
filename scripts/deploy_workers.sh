#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# deploy_workers.sh — Deploy mascarade worker agent to cluster nodes
#
# Supports:
#   - Linux nodes (systemd): Tower, KXKM-AI
#   - macOS nodes (launchd): CILS, GrosMac (local)
#   - TUI menu: deploy-all, deploy-one, status, stop, restart, logs
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKER_SCRIPT="$PROJECT_ROOT/scripts/worker_agent.py"
DEPLOY_DIR="$PROJECT_ROOT/deploy/worker-agent"
REQUIREMENTS="$DEPLOY_DIR/requirements.txt"
SYSTEMD_UNIT="$DEPLOY_DIR/mascarade-worker.service"
LAUNCHD_PLIST="$DEPLOY_DIR/com.mascarade.worker.plist"
LOG_FILE="$PROJECT_ROOT/logs/deploy_workers_$(date +%Y%m%d_%H%M%S).log"

# ── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Node definitions ────────────────────────────────────────────────
# Format: NAME|SSH_TARGET|AUTH_METHOD|PASSWORD|REMOTE_USER|REMOTE_HOME
declare -a NODES=(
    "GrosMac|local|local||electron|/Users/electron"
    "CILS|cils@192.168.0.210|sshpass|oeil|cils|/Users/cils"
    "Tower|clems@192.168.0.120|sshpass|iamall06|clems|/home/clems"
    "KXKM-AI|kxkm@kxkm-ai|key||kxkm|/home/kxkm"
)

WORKER_PORT=8201
SERVICE_NAME="mascarade-worker"
PLIST_LABEL="com.mascarade.worker"

# ── Helpers ──────────────────────────────────────────────────────────

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] $*" >> "$LOG_FILE"
}

info()    { echo -e "${BLUE}[INFO]${RESET}  $*"; log "INFO  $*"; }
ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; log "OK    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; log "WARN  $*"; }
fail()    { echo -e "${RED}[FAIL]${RESET}  $*"; log "FAIL  $*"; }
header()  { echo -e "\n${BOLD}${CYAN}═══ $* ═══${RESET}\n"; log "===== $* ====="; }

# Parse node string into variables
parse_node() {
    local IFS='|'
    read -r NODE_NAME NODE_SSH NODE_AUTH NODE_PASS NODE_USER NODE_HOME <<< "$1"
}

# Execute command on a node (local or remote)
run_on() {
    local node_def="$1"
    shift
    parse_node "$node_def"

    if [[ "$NODE_AUTH" == "local" ]]; then
        eval "$@" 2>&1
    elif [[ "$NODE_AUTH" == "sshpass" ]]; then
        sshpass -p "$NODE_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$NODE_SSH" "$@" 2>&1
    elif [[ "$NODE_AUTH" == "key" ]]; then
        ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$NODE_SSH" "$@" 2>&1
    fi
}

# Copy file to a node
copy_to() {
    local node_def="$1"
    local src="$2"
    local dst="$3"
    parse_node "$node_def"

    if [[ "$NODE_AUTH" == "local" ]]; then
        cp "$src" "$dst"
    elif [[ "$NODE_AUTH" == "sshpass" ]]; then
        sshpass -p "$NODE_PASS" scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$src" "${NODE_SSH}:${dst}" 2>&1
    elif [[ "$NODE_AUTH" == "key" ]]; then
        scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$src" "${NODE_SSH}:${dst}" 2>&1
    fi
}

# Detect remote OS
detect_os() {
    local node_def="$1"
    run_on "$node_def" "uname -s" 2>/dev/null | tr -d '[:space:]'
}

# ── Preflight checks ────────────────────────────────────────────────

preflight() {
    local errors=0

    if [[ ! -f "$WORKER_SCRIPT" ]]; then
        fail "worker_agent.py not found at $WORKER_SCRIPT"
        ((errors++))
    fi
    if [[ ! -f "$REQUIREMENTS" ]]; then
        fail "requirements.txt not found at $REQUIREMENTS"
        ((errors++))
    fi
    if ! command -v sshpass &>/dev/null; then
        warn "sshpass not installed — password-based SSH will fail"
        warn "Install with: brew install sshpass  (or: apt install sshpass)"
    fi

    if ((errors > 0)); then
        fail "Preflight failed with $errors error(s). Aborting."
        exit 1
    fi
}

# ── Deploy to a single node ─────────────────────────────────────────

deploy_node() {
    local node_def="$1"
    parse_node "$node_def"
    local worker_dir="${NODE_HOME}/mascarade-worker"

    header "Deploying to ${NODE_NAME}"

    # 1. Test connectivity
    info "Testing connectivity to ${NODE_NAME}..."
    if ! run_on "$node_def" "echo ok" &>/dev/null; then
        fail "Cannot reach ${NODE_NAME} (${NODE_SSH})"
        return 1
    fi
    ok "Connected to ${NODE_NAME}"

    # 2. Detect OS
    local os
    os="$(detect_os "$node_def")"
    info "Detected OS: ${os}"

    # 3. Create working directory
    info "Creating ${worker_dir}..."
    run_on "$node_def" "mkdir -p '${worker_dir}'" || true

    # 4. Copy files
    info "Copying worker_agent.py..."
    copy_to "$node_def" "$WORKER_SCRIPT" "${worker_dir}/worker_agent.py"
    ok "worker_agent.py copied"

    info "Copying requirements.txt..."
    copy_to "$node_def" "$REQUIREMENTS" "${worker_dir}/requirements.txt"
    ok "requirements.txt copied"

    # 5. Install dependencies
    info "Installing Python dependencies..."
    if ! run_on "$node_def" "cd '${worker_dir}' && python3 -m pip install --user --break-system-packages -r requirements.txt 2>&1 || python3 -m pip install --user -r requirements.txt 2>&1 || pip3 install --user -r requirements.txt 2>&1" >/dev/null; then
        warn "pip install had warnings (may still be OK)"
    fi
    ok "Dependencies installed"

    # 6. Install service
    if [[ "$os" == "Darwin" ]]; then
        install_launchd "$node_def" "$worker_dir"
    elif [[ "$os" == "Linux" ]]; then
        install_systemd "$node_def" "$worker_dir"
    else
        fail "Unknown OS '$os' on ${NODE_NAME}"
        return 1
    fi

    # 7. Health check
    verify_health "$node_def"
}

# ── systemd (Linux) ─────────────────────────────────────────────────

install_systemd() {
    local node_def="$1"
    local worker_dir="$2"
    parse_node "$node_def"

    info "Installing systemd service on ${NODE_NAME}..."

    # Stop existing service if running
    run_on "$node_def" "sudo systemctl stop ${SERVICE_NAME} 2>/dev/null || true"

    # Generate unit file with correct user and paths
    local unit_content
    unit_content="$(cat <<UNIT
[Unit]
Description=Mascarade Worker Agent
Documentation=https://github.com/electron-rare/mascarade
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${NODE_USER}
WorkingDirectory=${worker_dir}
ExecStart=/usr/bin/python3 ${worker_dir}/worker_agent.py --port ${WORKER_PORT} --runtime auto
Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/usr/local/bin:/usr/bin:/bin:/home/${NODE_USER}/.local/bin
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
UNIT
)"

    # Write unit file via heredoc over SSH
    echo "$unit_content" | if [[ "$NODE_AUTH" == "sshpass" ]]; then
        sshpass -p "$NODE_PASS" ssh -o StrictHostKeyChecking=no "$NODE_SSH" "sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null"
    else
        ssh -o StrictHostKeyChecking=no "$NODE_SSH" "sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null"
    fi

    run_on "$node_def" "sudo systemctl daemon-reload"
    run_on "$node_def" "sudo systemctl enable ${SERVICE_NAME}"
    run_on "$node_def" "sudo systemctl start ${SERVICE_NAME}"

    ok "systemd service installed and started on ${NODE_NAME}"
}

# ── launchd (macOS) ──────────────────────────────────────────────────

install_launchd() {
    local node_def="$1"
    local worker_dir="$2"
    parse_node "$node_def"

    local plist_dst
    local log_dir="${worker_dir}/logs"

    info "Installing launchd service on ${NODE_NAME}..."

    # Unload existing plist if loaded
    if [[ "$NODE_AUTH" == "local" ]]; then
        plist_dst="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
        launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true
        mkdir -p "$log_dir"
    else
        plist_dst="${NODE_HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
        run_on "$node_def" "launchctl bootout gui/\$(id -u)/${PLIST_LABEL} 2>/dev/null || true"
        run_on "$node_def" "mkdir -p '${log_dir}'"
        run_on "$node_def" "mkdir -p '${NODE_HOME}/Library/LaunchAgents'"
    fi

    # Generate plist with correct paths
    local plist_content
    plist_content="$(cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${worker_dir}/worker_agent.py</string>
        <string>--port</string>
        <string>${WORKER_PORT}</string>
        <string>--runtime</string>
        <string>auto</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${worker_dir}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>5</integer>

    <key>StandardOutPath</key>
    <string>${log_dir}/mascarade-worker.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${log_dir}/mascarade-worker.stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:${NODE_HOME}/.local/bin:${NODE_HOME}/Library/Python/3.11/bin</string>
    </dict>
</dict>
</plist>
PLIST
)"

    if [[ "$NODE_AUTH" == "local" ]]; then
        echo "$plist_content" > "$plist_dst"
        launchctl bootstrap "gui/$(id -u)" "$plist_dst"
    else
        echo "$plist_content" | if [[ "$NODE_AUTH" == "sshpass" ]]; then
            sshpass -p "$NODE_PASS" ssh -o StrictHostKeyChecking=no "$NODE_SSH" "cat > '${plist_dst}'"
        else
            ssh -o StrictHostKeyChecking=no "$NODE_SSH" "cat > '${plist_dst}'"
        fi
        run_on "$node_def" "launchctl bootstrap gui/\$(id -u) '${plist_dst}'"
    fi

    ok "launchd service installed and started on ${NODE_NAME}"
}

# ── Health check ─────────────────────────────────────────────────────

verify_health() {
    local node_def="$1"
    parse_node "$node_def"

    info "Waiting for health endpoint on ${NODE_NAME}..."

    local target
    if [[ "$NODE_AUTH" == "local" ]]; then
        target="http://127.0.0.1:${WORKER_PORT}/health"
    else
        # Extract host from SSH target (user@host)
        local host="${NODE_SSH#*@}"
        target="http://${host}:${WORKER_PORT}/health"
    fi

    local attempts=0
    local max_attempts=10
    while ((attempts < max_attempts)); do
        ((attempts++))
        if curl -sf --connect-timeout 3 "$target" &>/dev/null; then
            local status
            status="$(curl -sf "$target" 2>/dev/null)"
            ok "Health OK on ${NODE_NAME}: $(echo "$status" | python3 -c "import sys,json;d=json.load(sys.stdin);print(f'runtime={d.get(\"runtime\",\"?\")}, ram_free={d.get(\"ram_free_mb\",0)}MB')" 2>/dev/null || echo "$status")"
            return 0
        fi
        sleep 2
    done

    warn "Health check failed on ${NODE_NAME} after ${max_attempts} attempts (service may still be starting)"
    return 1
}

# ── Status / Stop / Restart / Logs ───────────────────────────────────

node_status() {
    local node_def="$1"
    parse_node "$node_def"

    local os
    os="$(detect_os "$node_def" 2>/dev/null || echo "unknown")"

    printf "  ${BOLD}%-12s${RESET} " "${NODE_NAME}"

    # Check connectivity
    if ! run_on "$node_def" "echo ok" &>/dev/null; then
        echo -e "${RED}UNREACHABLE${RESET}"
        return
    fi

    # Check service status
    local svc_status="unknown"
    if [[ "$os" == "Darwin" ]]; then
        if run_on "$node_def" "launchctl print gui/\$(id -u)/${PLIST_LABEL}" &>/dev/null; then
            svc_status="loaded"
        else
            svc_status="not loaded"
        fi
    elif [[ "$os" == "Linux" ]]; then
        if run_on "$node_def" "systemctl is-active ${SERVICE_NAME}" 2>/dev/null | grep -q "active"; then
            svc_status="active"
        else
            svc_status="inactive"
        fi
    fi

    # Check health endpoint
    local health_ok=false
    local target
    if [[ "$NODE_AUTH" == "local" ]]; then
        target="http://127.0.0.1:${WORKER_PORT}/health"
    else
        local host="${NODE_SSH#*@}"
        target="http://${host}:${WORKER_PORT}/health"
    fi

    if curl -sf --connect-timeout 3 "$target" &>/dev/null; then
        health_ok=true
    fi

    if $health_ok; then
        local info_str
        info_str="$(curl -sf "$target" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
rt=d.get('runtime','?')
ram=d.get('ram_free_mb',0)
up=d.get('uptime_s',0)
models=','.join(d.get('loaded_models',[])) or 'none'
print(f'runtime={rt} ram_free={ram}MB uptime={up}s models={models}')
" 2>/dev/null || echo "")"
        echo -e "${GREEN}HEALTHY${RESET}  (svc=${svc_status}) ${DIM}${info_str}${RESET}"
    elif [[ "$svc_status" == "active" || "$svc_status" == "loaded" ]]; then
        echo -e "${YELLOW}SVC UP / NO HEALTH${RESET}  (svc=${svc_status})"
    else
        echo -e "${RED}DOWN${RESET}  (svc=${svc_status})"
    fi
}

stop_node() {
    local node_def="$1"
    parse_node "$node_def"

    local os
    os="$(detect_os "$node_def" 2>/dev/null || echo "unknown")"

    info "Stopping ${NODE_NAME}..."
    if [[ "$os" == "Darwin" ]]; then
        run_on "$node_def" "launchctl bootout gui/\$(id -u)/${PLIST_LABEL} 2>/dev/null || true"
    elif [[ "$os" == "Linux" ]]; then
        run_on "$node_def" "sudo systemctl stop ${SERVICE_NAME} 2>/dev/null || true"
    fi
    ok "Stopped ${NODE_NAME}"
}

restart_node() {
    local node_def="$1"
    parse_node "$node_def"

    local os
    os="$(detect_os "$node_def" 2>/dev/null || echo "unknown")"

    info "Restarting ${NODE_NAME}..."
    if [[ "$os" == "Darwin" ]]; then
        local plist_path="${NODE_HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
        run_on "$node_def" "launchctl bootout gui/\$(id -u)/${PLIST_LABEL} 2>/dev/null || true"
        sleep 1
        run_on "$node_def" "launchctl bootstrap gui/\$(id -u) '${plist_path}'"
    elif [[ "$os" == "Linux" ]]; then
        run_on "$node_def" "sudo systemctl restart ${SERVICE_NAME}"
    fi
    ok "Restarted ${NODE_NAME}"
}

show_logs() {
    local node_def="$1"
    local lines="${2:-50}"
    parse_node "$node_def"

    local os
    os="$(detect_os "$node_def" 2>/dev/null || echo "unknown")"

    header "Logs from ${NODE_NAME} (last ${lines} lines)"
    if [[ "$os" == "Darwin" ]]; then
        local log_path="${NODE_HOME}/mascarade-worker/logs/mascarade-worker.stderr.log"
        run_on "$node_def" "tail -n ${lines} '${log_path}' 2>/dev/null || echo '(no logs found)'"
    elif [[ "$os" == "Linux" ]]; then
        run_on "$node_def" "sudo journalctl -u ${SERVICE_NAME} --no-pager -n ${lines} 2>/dev/null || echo '(no logs found)'"
    fi
}

# ── Node picker ──────────────────────────────────────────────────────

pick_node() {
    echo ""
    echo -e "${BOLD}Select a node:${RESET}"
    local i=1
    for node in "${NODES[@]}"; do
        parse_node "$node"
        printf "  ${CYAN}%d${RESET}) %s ${DIM}(%s)${RESET}\n" "$i" "$NODE_NAME" "$NODE_SSH"
        ((i++))
    done
    echo ""
    read -rp "Node number [1-${#NODES[@]}]: " choice

    if [[ "$choice" -ge 1 && "$choice" -le "${#NODES[@]}" ]] 2>/dev/null; then
        SELECTED_NODE="${NODES[$((choice - 1))]}"
        return 0
    else
        fail "Invalid selection"
        return 1
    fi
}

# ── Batch operations ─────────────────────────────────────────────────

deploy_all() {
    header "Deploy All Nodes"
    local ok_count=0
    local fail_count=0
    for node in "${NODES[@]}"; do
        if deploy_node "$node"; then
            ((ok_count++))
        else
            ((fail_count++))
        fi
    done
    echo ""
    info "Deployment complete: ${GREEN}${ok_count} succeeded${RESET}, ${RED}${fail_count} failed${RESET}"
}

status_all() {
    header "Cluster Status"
    for node in "${NODES[@]}"; do
        node_status "$node"
    done
    echo ""
}

stop_all() {
    header "Stop All Workers"
    for node in "${NODES[@]}"; do
        stop_node "$node"
    done
}

restart_all() {
    header "Restart All Workers"
    for node in "${NODES[@]}"; do
        restart_node "$node"
    done
}

# ── TUI Menu ─────────────────────────────────────────────────────────

show_menu() {
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${CYAN}║   Mascarade Worker Agent — Deployer      ║${RESET}"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════╣${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${GREEN}1${RESET}) Deploy all nodes                    ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${GREEN}2${RESET}) Deploy single node                  ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${BLUE}3${RESET}) Status (all nodes)                  ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${YELLOW}4${RESET}) Stop single node                   ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${YELLOW}5${RESET}) Stop all nodes                     ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${YELLOW}6${RESET}) Restart single node                ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${YELLOW}7${RESET}) Restart all nodes                  ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${DIM}8${RESET}) View logs (single node)             ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}║${RESET}  ${RED}q${RESET}) Quit                               ${BOLD}${CYAN}║${RESET}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${RESET}"
    echo ""
}

interactive_menu() {
    while true; do
        show_menu
        read -rp "Choice: " action
        case "$action" in
            1) deploy_all ;;
            2)
                if pick_node; then
                    deploy_node "$SELECTED_NODE"
                fi
                ;;
            3) status_all ;;
            4)
                if pick_node; then
                    stop_node "$SELECTED_NODE"
                fi
                ;;
            5) stop_all ;;
            6)
                if pick_node; then
                    restart_node "$SELECTED_NODE"
                fi
                ;;
            7) restart_all ;;
            8)
                if pick_node; then
                    show_logs "$SELECTED_NODE"
                fi
                ;;
            q|Q) echo -e "${DIM}Bye.${RESET}"; exit 0 ;;
            *) warn "Unknown option: $action" ;;
        esac
    done
}

# ── CLI entrypoint ───────────────────────────────────────────────────

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  deploy-all    Deploy to all nodes"
    echo "  deploy-one    Deploy to a single node (interactive)"
    echo "  status        Show status of all nodes"
    echo "  stop          Stop all workers"
    echo "  restart       Restart all workers"
    echo "  logs          View logs from a node (interactive)"
    echo "  (none)        Interactive TUI menu"
}

main() {
    preflight

    case "${1:-}" in
        deploy-all)  deploy_all ;;
        deploy-one)
            if pick_node; then
                deploy_node "$SELECTED_NODE"
            fi
            ;;
        status)      status_all ;;
        stop)        stop_all ;;
        restart)     restart_all ;;
        logs)
            if pick_node; then
                show_logs "$SELECTED_NODE"
            fi
            ;;
        -h|--help)   usage ;;
        "")          interactive_menu ;;
        *)
            fail "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

main "$@"
