#!/usr/bin/env bash
# ============================================================================
# setup_exo_cluster.sh — Install, configure, and manage an Exo distributed
# inference cluster for the mascarade Mac fleet.
#
# Nodes:
#   - GrosMac (local)          — coordinator + worker
#   - CILS   (192.168.0.210)   — worker
#   - Tower  (192.168.0.120)   — worker
#
# Usage:
#   ./scripts/setup_exo_cluster.sh install       # Install Exo on local node
#   ./scripts/setup_exo_cluster.sh install-all    # Install on all nodes via SSH
#   ./scripts/setup_exo_cluster.sh start          # Start Exo on local node
#   ./scripts/setup_exo_cluster.sh stop           # Stop Exo on local node
#   ./scripts/setup_exo_cluster.sh start-all      # Start on all nodes
#   ./scripts/setup_exo_cluster.sh stop-all       # Stop on all nodes
#   ./scripts/setup_exo_cluster.sh status         # Cluster health check
#   ./scripts/setup_exo_cluster.sh download-model <model_id>
#   ./scripts/setup_exo_cluster.sh logs           # Tail local Exo logs
# ============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXO_REPO="https://github.com/exo-explore/exo.git"
EXO_INSTALL_DIR="${EXO_INSTALL_DIR:-$HOME/.exo/src}"
EXO_MODELS_DIR="${EXO_MODELS_DIR:-$HOME/.exo/models}"
EXO_PORT=52415
EXO_NAMESPACE="${EXO_NAMESPACE:-mascarade}"
EXO_LOG_DIR="${EXO_LOG_DIR:-$HOME/.exo/logs}"
EXO_PID_FILE="${EXO_PID_FILE:-$HOME/.exo/exo.pid}"

# Cluster nodes — adjust as needed
NODES=(
    "local"
    "cils@192.168.0.210"
    "clems@192.168.0.120"
)

NODE_NAMES=(
    "GrosMac"
    "CILS"
    "Tower"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_info()  { echo -e "${GREEN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%H:%M:%S') $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $*"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $(date '+%H:%M:%S') $*"; }

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------
check_prereqs() {
    log_step "Checking prerequisites..."
    local missing=0

    if ! command -v git &>/dev/null; then
        log_error "git not found"
        missing=1
    fi

    if ! command -v uv &>/dev/null; then
        log_warn "uv not found — installing..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi

    if ! command -v node &>/dev/null; then
        log_error "Node.js not found — install via: brew install node"
        missing=1
    fi

    if ! command -v npm &>/dev/null; then
        log_error "npm not found — install via: brew install node"
        missing=1
    fi

    if ! command -v rustc &>/dev/null; then
        log_warn "Rust not found — installing nightly..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly
        source "$HOME/.cargo/env"
    fi

    # Check for Rust nightly
    if command -v rustup &>/dev/null; then
        if ! rustup toolchain list | grep -q nightly; then
            log_warn "Installing Rust nightly toolchain..."
            rustup toolchain install nightly
        fi
    fi

    if [[ "$(uname)" == "Darwin" ]]; then
        if ! xcode-select -p &>/dev/null; then
            log_error "Xcode command line tools not found — install via: xcode-select --install"
            missing=1
        fi

        if ! command -v macmon &>/dev/null; then
            log_warn "macmon not found — installing via brew..."
            brew install vladkens/tap/macmon 2>/dev/null || log_warn "macmon install failed (optional)"
        fi
    fi

    if [[ "$missing" -eq 1 ]]; then
        log_error "Missing prerequisites. Install them and re-run."
        exit 1
    fi

    log_info "All prerequisites satisfied."
}

# ---------------------------------------------------------------------------
# Install Exo (local node)
# ---------------------------------------------------------------------------
install_local() {
    check_prereqs

    log_step "Installing Exo to ${EXO_INSTALL_DIR}..."

    mkdir -p "$(dirname "$EXO_INSTALL_DIR")"
    mkdir -p "$EXO_MODELS_DIR"
    mkdir -p "$EXO_LOG_DIR"

    if [[ -d "$EXO_INSTALL_DIR/.git" ]]; then
        log_info "Exo repo already cloned — pulling latest..."
        cd "$EXO_INSTALL_DIR"
        git pull --rebase origin main
    else
        log_info "Cloning Exo repository..."
        git clone "$EXO_REPO" "$EXO_INSTALL_DIR"
        cd "$EXO_INSTALL_DIR"
    fi

    # Build dashboard
    log_step "Building Exo dashboard..."
    cd "$EXO_INSTALL_DIR/dashboard"
    npm install --silent
    npm run build

    cd "$EXO_INSTALL_DIR"

    # Verify it starts (dry run)
    log_step "Verifying Exo installation..."
    timeout 10 uv run exo --help &>/dev/null && log_info "Exo binary verified." || log_warn "Exo --help check inconclusive (may still work)."

    log_info "Exo installed successfully at ${EXO_INSTALL_DIR}"
    log_info "Models directory: ${EXO_MODELS_DIR}"
    log_info "Cluster namespace: ${EXO_NAMESPACE}"
}

# ---------------------------------------------------------------------------
# Install on remote node via SSH
# ---------------------------------------------------------------------------
install_remote() {
    local ssh_target="$1"
    local node_name="$2"

    log_step "Installing Exo on ${node_name} (${ssh_target})..."

    # Copy this script to the remote and run it
    scp -q "$0" "${ssh_target}:/tmp/setup_exo_cluster.sh"
    ssh -t "${ssh_target}" "chmod +x /tmp/setup_exo_cluster.sh && EXO_NAMESPACE=${EXO_NAMESPACE} /tmp/setup_exo_cluster.sh install"
}

# ---------------------------------------------------------------------------
# Install on all nodes
# ---------------------------------------------------------------------------
install_all() {
    log_step "Installing Exo on all cluster nodes..."

    for i in "${!NODES[@]}"; do
        local node="${NODES[$i]}"
        local name="${NODE_NAMES[$i]}"

        if [[ "$node" == "local" ]]; then
            install_local
        else
            install_remote "$node" "$name"
        fi
    done

    log_info "Exo installed on all nodes."
}

# ---------------------------------------------------------------------------
# Start Exo (local node)
# ---------------------------------------------------------------------------
start_local() {
    if is_running; then
        log_warn "Exo is already running (PID $(cat "$EXO_PID_FILE"))"
        return 0
    fi

    if [[ ! -d "$EXO_INSTALL_DIR/.git" ]]; then
        log_error "Exo not installed. Run: $0 install"
        exit 1
    fi

    mkdir -p "$EXO_LOG_DIR"

    log_step "Starting Exo node..."
    log_info "Namespace: ${EXO_NAMESPACE}"
    log_info "Port: ${EXO_PORT}"
    log_info "Models dir: ${EXO_MODELS_DIR}"

    cd "$EXO_INSTALL_DIR"

    # Export Exo configuration
    export EXO_LIBP2P_NAMESPACE="$EXO_NAMESPACE"
    export EXO_MODELS_DIR="$EXO_MODELS_DIR"

    local log_file="${EXO_LOG_DIR}/exo_$(date '+%Y%m%d_%H%M%S').log"

    nohup uv run exo > "$log_file" 2>&1 &
    local pid=$!
    echo "$pid" > "$EXO_PID_FILE"

    # Wait for startup
    log_info "Waiting for Exo to start (PID ${pid})..."
    local retries=0
    local max_retries=30
    while [[ $retries -lt $max_retries ]]; do
        if curl -s "http://localhost:${EXO_PORT}/models" &>/dev/null; then
            log_info "Exo started successfully on port ${EXO_PORT}"
            log_info "Dashboard: http://localhost:${EXO_PORT}"
            log_info "Log file: ${log_file}"
            return 0
        fi
        sleep 2
        retries=$((retries + 1))
    done

    log_error "Exo failed to start within ${max_retries}x2 seconds. Check ${log_file}"
    return 1
}

# ---------------------------------------------------------------------------
# Stop Exo (local node)
# ---------------------------------------------------------------------------
stop_local() {
    if [[ -f "$EXO_PID_FILE" ]]; then
        local pid
        pid=$(cat "$EXO_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log_step "Stopping Exo (PID ${pid})..."
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "Graceful shutdown failed, sending SIGKILL..."
                kill -9 "$pid" 2>/dev/null || true
            fi
            log_info "Exo stopped."
        else
            log_warn "Exo process ${pid} not found (stale PID file)."
        fi
        rm -f "$EXO_PID_FILE"
    else
        # Try to find by port
        local pid
        pid=$(lsof -ti ":${EXO_PORT}" 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            log_step "Stopping Exo (PID ${pid}, found by port)..."
            kill "$pid"
            sleep 2
            log_info "Exo stopped."
        else
            log_info "Exo is not running."
        fi
    fi
}

# ---------------------------------------------------------------------------
# Start/Stop on remote node
# ---------------------------------------------------------------------------
start_remote() {
    local ssh_target="$1"
    local node_name="$2"
    log_step "Starting Exo on ${node_name} (${ssh_target})..."
    ssh "${ssh_target}" "cd ~/.exo/src && EXO_LIBP2P_NAMESPACE=${EXO_NAMESPACE} EXO_MODELS_DIR=~/.exo/models nohup uv run exo > ~/.exo/logs/exo_\$(date '+%Y%m%d_%H%M%S').log 2>&1 & echo \$! > ~/.exo/exo.pid"
    log_info "Exo started on ${node_name}."
}

stop_remote() {
    local ssh_target="$1"
    local node_name="$2"
    log_step "Stopping Exo on ${node_name} (${ssh_target})..."
    ssh "${ssh_target}" 'if [ -f ~/.exo/exo.pid ]; then kill $(cat ~/.exo/exo.pid) 2>/dev/null; rm -f ~/.exo/exo.pid; echo "Stopped"; else echo "Not running"; fi'
}

# ---------------------------------------------------------------------------
# Start/Stop all nodes
# ---------------------------------------------------------------------------
start_all() {
    log_step "Starting Exo on all cluster nodes..."
    for i in "${!NODES[@]}"; do
        local node="${NODES[$i]}"
        local name="${NODE_NAMES[$i]}"
        if [[ "$node" == "local" ]]; then
            start_local
        else
            start_remote "$node" "$name"
        fi
    done
    log_info "All nodes started. Waiting for peer discovery..."
    sleep 5
    health_check
}

stop_all() {
    log_step "Stopping Exo on all cluster nodes..."
    for i in "${!NODES[@]}"; do
        local node="${NODES[$i]}"
        local name="${NODE_NAMES[$i]}"
        if [[ "$node" == "local" ]]; then
            stop_local
        else
            stop_remote "$node" "$name"
        fi
    done
    log_info "All nodes stopped."
}

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
is_running() {
    if [[ -f "$EXO_PID_FILE" ]] && kill -0 "$(cat "$EXO_PID_FILE")" 2>/dev/null; then
        return 0
    fi
    return 1
}

health_check() {
    log_step "Cluster health check..."
    echo ""

    local all_ok=0

    for i in "${!NODES[@]}"; do
        local node="${NODES[$i]}"
        local name="${NODE_NAMES[$i]}"
        local url

        if [[ "$node" == "local" ]]; then
            url="http://localhost:${EXO_PORT}"
        else
            local host
            host=$(echo "$node" | cut -d'@' -f2)
            url="http://${host}:${EXO_PORT}"
        fi

        printf "  %-12s %-25s " "$name" "$url"

        local response
        response=$(curl -s --connect-timeout 5 --max-time 10 "${url}/models" 2>/dev/null) || true

        if [[ -n "$response" ]]; then
            local model_count
            model_count=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d, list) else 'N/A')" 2>/dev/null || echo "?")
            echo -e "${GREEN}OK${NC}  (${model_count} models)"
        else
            echo -e "${RED}UNREACHABLE${NC}"
            all_ok=1
        fi
    done

    echo ""

    # Check cluster state from local node
    if curl -s --connect-timeout 3 "http://localhost:${EXO_PORT}/state" &>/dev/null; then
        log_info "Cluster state endpoint responding."
        local state
        state=$(curl -s "http://localhost:${EXO_PORT}/state" 2>/dev/null)
        if [[ -n "$state" ]]; then
            echo "  Cluster state (raw): $(echo "$state" | head -c 200)"
        fi
    fi

    echo ""
    if [[ "$all_ok" -eq 0 ]]; then
        log_info "All nodes healthy."
    else
        log_warn "Some nodes unreachable."
    fi

    return "$all_ok"
}

# ---------------------------------------------------------------------------
# Download model (via Exo API)
# ---------------------------------------------------------------------------
download_model() {
    local model_id="${1:?Usage: $0 download-model <model_id>}"

    if ! curl -s "http://localhost:${EXO_PORT}/models" &>/dev/null; then
        log_error "Exo is not running locally. Start it first: $0 start"
        exit 1
    fi

    log_step "Adding model: ${model_id}..."

    local response
    response=$(curl -s -X POST "http://localhost:${EXO_PORT}/models/add" \
        -H 'Content-Type: application/json' \
        -d "{\"model_id\": \"${model_id}\"}")

    echo "Response: $response"
    log_info "Model registration complete. Exo will download on first use or check /models for status."
}

# ---------------------------------------------------------------------------
# Tail logs
# ---------------------------------------------------------------------------
tail_logs() {
    local latest_log
    latest_log=$(ls -t "${EXO_LOG_DIR}"/exo_*.log 2>/dev/null | head -1)

    if [[ -z "$latest_log" ]]; then
        log_error "No log files found in ${EXO_LOG_DIR}"
        exit 1
    fi

    log_info "Tailing ${latest_log}..."
    tail -f "$latest_log"
}

# ---------------------------------------------------------------------------
# Quick test — send a prompt via OpenAI-compatible API
# ---------------------------------------------------------------------------
test_inference() {
    local model="${1:-mlx-community/Llama-3.2-1B-Instruct-4bit}"

    if ! curl -s "http://localhost:${EXO_PORT}/models" &>/dev/null; then
        log_error "Exo is not running locally."
        exit 1
    fi

    log_step "Testing inference with model: ${model}..."

    local response
    response=$(curl -s -X POST "http://localhost:${EXO_PORT}/v1/chat/completions" \
        -H 'Content-Type: application/json' \
        -d "{
            \"model\": \"${model}\",
            \"messages\": [{\"role\": \"user\", \"content\": \"Say hello in exactly 5 words.\"}],
            \"max_tokens\": 50,
            \"temperature\": 0.7
        }")

    echo ""
    echo "Response:"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local command="${1:-help}"

    case "$command" in
        install)
            install_local
            ;;
        install-all)
            install_all
            ;;
        start)
            start_local
            ;;
        stop)
            stop_local
            ;;
        start-all)
            start_all
            ;;
        stop-all)
            stop_all
            ;;
        restart)
            stop_local
            sleep 2
            start_local
            ;;
        status|health)
            health_check
            ;;
        download-model)
            download_model "${2:-}"
            ;;
        logs)
            tail_logs
            ;;
        test)
            test_inference "${2:-}"
            ;;
        help|--help|-h)
            echo ""
            echo "Exo Cluster Manager for Mascarade"
            echo "================================="
            echo ""
            echo "Usage: $0 <command> [args]"
            echo ""
            echo "Commands:"
            echo "  install          Install Exo on local node"
            echo "  install-all      Install Exo on all cluster nodes (SSH)"
            echo "  start            Start Exo on local node"
            echo "  stop             Stop Exo on local node"
            echo "  start-all        Start Exo on all cluster nodes"
            echo "  stop-all         Stop Exo on all cluster nodes"
            echo "  restart          Restart Exo on local node"
            echo "  status           Cluster health check"
            echo "  download-model   Register a HuggingFace model (e.g. mlx-community/Llama-3.2-1B-Instruct-4bit)"
            echo "  logs             Tail local Exo logs"
            echo "  test [model]     Run a quick inference test"
            echo "  help             Show this help"
            echo ""
            echo "Environment:"
            echo "  EXO_INSTALL_DIR   Installation path (default: ~/.exo/src)"
            echo "  EXO_MODELS_DIR    Model storage (default: ~/.exo/models)"
            echo "  EXO_NAMESPACE     Cluster namespace (default: mascarade)"
            echo "  EXO_LOG_DIR       Log directory (default: ~/.exo/logs)"
            echo "  EXO_PORT          API port (default: 52415)"
            echo ""
            echo "Cluster nodes:"
            for i in "${!NODES[@]}"; do
                echo "  ${NODE_NAMES[$i]}: ${NODES[$i]}"
            done
            echo ""
            ;;
        *)
            log_error "Unknown command: ${command}"
            echo "Run '$0 help' for usage."
            exit 1
            ;;
    esac
}

main "$@"
