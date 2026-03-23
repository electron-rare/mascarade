#!/usr/bin/env bash
# =============================================================================
# scripts/apple_intelligence_tui.sh
# Apple Intelligence Integration TUI for Mascarade
#
# Interactive terminal interface for managing Apple Intelligence components:
#   - MLX-LM server management
#   - Exo distributed inference cluster
#   - CoreML / Foundation Models bridge
#   - Model registry (HF -> MLX -> GGUF conversion pipeline)
#   - Benchmark suite
#   - Structured logging with rotation
#   - Health checks for all services + P2P mesh
#
# Usage:
#   ./scripts/apple_intelligence_tui.sh [--help]
#
# Requires: macOS (Darwin), bash 4+, curl
# =============================================================================
set -euo pipefail

# ── Root paths ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/apple_intelligence_tui.log"
LOG_MAX_SIZE=$((10 * 1024 * 1024))  # 10 MB
LOG_KEEP_COUNT=5

# ── Default ports/URLs ──
MASCARADE_CORE_URL="${MASCARADE_CORE_URL:-http://localhost:8100}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
MLX_LM_URL="${MLX_LM_URL:-http://localhost:8201}"
APPLE_LLM_URL="${APPLE_LLM_URL:-http://localhost:8201}"
EXO_URL="${EXO_URL:-http://localhost:52415}"
MODELS_ROOT="${APPLE_MODELS_ROOT:-${HOME}/Models/mascarade/apple-llm}"

# ── Terminal dimensions ──
TERM_COLS="${COLUMNS:-$(tput cols 2>/dev/null || echo 80)}"
TERM_ROWS="${LINES:-$(tput lines 2>/dev/null || echo 24)}"

# ── ANSI color codes (respect NO_COLOR) ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m'
    DIM='\033[2m'
    UNDERLINE='\033[4m'
    BLINK='\033[5m'
    REVERSE='\033[7m'
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    WHITE='\033[1;37m'
    GRAY='\033[0;90m'
    BG_RED='\033[41m'
    BG_GREEN='\033[42m'
    BG_YELLOW='\033[43m'
    BG_BLUE='\033[44m'
    NC='\033[0m'
else
    BOLD='' DIM='' UNDERLINE='' BLINK='' REVERSE=''
    RED='' GREEN='' YELLOW='' BLUE='' MAGENTA='' CYAN='' WHITE='' GRAY=''
    BG_RED='' BG_GREEN='' BG_YELLOW='' BG_BLUE='' NC=''
fi

# ── Status icons ──
ICON_OK="${GREEN}●${NC}"
ICON_WARN="${YELLOW}●${NC}"
ICON_ERR="${RED}●${NC}"
ICON_OFF="${GRAY}○${NC}"
ICON_ARROW="${CYAN}▸${NC}"

# =============================================================================
# LOGGING
# =============================================================================

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Rotate logs if the current log exceeds LOG_MAX_SIZE.
# Keeps the last LOG_KEEP_COUNT rotated files.
_log_rotate() {
    [[ -f "${LOG_FILE}" ]] || return 0
    local size
    size=$(stat -f%z "${LOG_FILE}" 2>/dev/null || stat --printf='%s' "${LOG_FILE}" 2>/dev/null || echo 0)
    if (( size > LOG_MAX_SIZE )); then
        # Shift existing rotated logs
        for i in $(seq $((LOG_KEEP_COUNT - 1)) -1 1); do
            local next=$((i + 1))
            [[ -f "${LOG_FILE}.${i}" ]] && mv "${LOG_FILE}.${i}" "${LOG_FILE}.${next}"
        done
        mv "${LOG_FILE}" "${LOG_FILE}.1"
        # Remove excess rotated logs
        for i in $(seq $((LOG_KEEP_COUNT + 1)) $((LOG_KEEP_COUNT + 5))); do
            rm -f "${LOG_FILE}.${i}"
        done
    fi
}

# Write a structured log entry with timestamp, level, and message.
_log() {
    local level="$1"
    shift
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    _log_rotate
    echo "[${ts}] [${level}] $*" >> "${LOG_FILE}"
}

log_info()    { _log "INFO"    "$@"; }
log_warn()    { _log "WARN"    "$@"; }
log_error()   { _log "ERROR"   "$@"; }
log_action()  { _log "ACTION"  "$@"; }
log_debug()   { _log "DEBUG"   "$@"; }

# =============================================================================
# DISPLAY HELPERS
# =============================================================================

# Clear screen and position cursor at top
cls() {
    printf '\033[2J\033[H'
}

# Draw a horizontal rule across the terminal
hr() {
    local char="${1:─}"
    printf '%*s\n' "${TERM_COLS}" '' | tr ' ' "${char}"
}

# Print centered text
center() {
    local text="$1"
    local width="${2:-${TERM_COLS}}"
    local stripped
    # Strip ANSI codes for length calculation
    stripped="$(echo -e "$text" | sed 's/\x1b\[[0-9;]*m//g')"
    local pad=$(( (width - ${#stripped}) / 2 ))
    (( pad < 0 )) && pad=0
    printf '%*s' "$pad" ''
    echo -e "$text"
}

# Print a box with title
box_header() {
    local title="$1"
    local width="${2:-60}"
    echo -e "${CYAN}┌$(printf '─%.0s' $(seq 1 $((width - 2))))┐${NC}"
    printf "${CYAN}│${NC} ${BOLD}%-$((width - 4))s${NC} ${CYAN}│${NC}\n" "$title"
    echo -e "${CYAN}├$(printf '─%.0s' $(seq 1 $((width - 2))))┤${NC}"
}

box_row() {
    local text="$1"
    local width="${2:-60}"
    local stripped
    stripped="$(echo -e "$text" | sed 's/\x1b\[[0-9;]*m//g')"
    local content_width=$((width - 4))
    # Pad to fill box width
    printf "${CYAN}│${NC} "
    echo -en "$text"
    local pad=$((content_width - ${#stripped}))
    (( pad < 0 )) && pad=0
    printf '%*s' "$pad" ''
    echo -e " ${CYAN}│${NC}"
}

box_footer() {
    local width="${1:-60}"
    echo -e "${CYAN}└$(printf '─%.0s' $(seq 1 $((width - 2))))┘${NC}"
}

# Print a section header
section_header() {
    local title="$1"
    echo ""
    echo -e "  ${MAGENTA}${BOLD}${title}${NC}"
    echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 50))${NC}"
}

# Print a menu item
menu_item() {
    local num="$1"
    local label="$2"
    local desc="${3:-}"
    echo -e "    ${GREEN}${BOLD}${num}${NC}  ${BOLD}${label}${NC}"
    if [[ -n "$desc" ]]; then
        echo -e "       ${DIM}${desc}${NC}"
    fi
}

# Prompt and read user choice
prompt_choice() {
    local prompt_text="${1:-Choice}"
    echo ""
    echo -en "  ${CYAN}${prompt_text}${NC} ${DIM}>${NC} "
    read -r choice
    echo "$choice"
}

# Wait for keypress
press_any_key() {
    echo ""
    echo -en "  ${DIM}Press any key to continue...${NC}"
    read -rsn1
}

# Show a spinner for a background operation (non-blocking display)
spinner() {
    local pid="$1"
    local msg="${2:-Working...}"
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYAN}${spin:i++%${#spin}:1}${NC} ${msg}"
        sleep 0.1
    done
    printf "\r  ${GREEN}●${NC} ${msg} done\n"
}

# =============================================================================
# BANNER
# =============================================================================

# Taglines from the mascarade MANIFEST
_TAGLINES=(
    "Don't Panic. -- H2G2"
    "42 secondes si tu es presse"
    "L'electron rare -- unstable by design"
    "KEEP THE BEAT -- BPM 125"
    "Si tu vois un plasma violet, c'est que tu es dans le groove."
    "Orchestration LLM agentic -- groove edition"
    "Apple Silicon x Neural Engine x MLX -- full local inference"
    "CoreML + Exo + MLX-LM -- the trifecta"
    "Fantasy neon, freaks rigoureux, pipeline propre"
)

banner() {
    local tagline="${_TAGLINES[RANDOM % ${#_TAGLINES[@]}]}"
    echo -e "${MAGENTA}${BOLD}"
    echo '    ╔══════════════════════════════════════════════════════════╗'
    echo '    ║                                                        ║'
    echo '    ║   ███╗   ███╗ █████╗ ███████╗ ██████╗ █████╗ ██████╗   ║'
    echo '    ║   ████╗ ████║██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗  ║'
    echo '    ║   ██╔████╔██║███████║███████╗██║     ███████║██████╔╝  ║'
    echo '    ║   ██║╚██╔╝██║██╔══██║╚════██║██║     ██╔══██║██╔══██╗  ║'
    echo '    ║   ██║ ╚═╝ ██║██║  ██║███████║╚██████╗██║  ██║██║  ██║  ║'
    echo '    ║   ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝  ║'
    echo '    ║                                                        ║'
    printf '    ║  %-54s  ║\n' "Apple Intelligence Integration TUI"
    echo '    ╚══════════════════════════════════════════════════════════╝'
    echo -e "${NC}"
    center "${DIM}${tagline}${NC}"
    echo ""
}

# =============================================================================
# SERVICE CHECKS (non-blocking, with timeouts)
# =============================================================================

# Check if a URL responds within timeout. Returns 0=ok, 1=down
_http_ok() {
    local url="$1"
    local timeout="${2:-3}"
    curl -sf --max-time "$timeout" "$url" >/dev/null 2>&1
}

# Check if a command exists
_cmd_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check MLX-LM Python package availability
check_mlx_lm_installed() {
    python3 -c "import mlx_lm" 2>/dev/null
}

# Check MLX framework availability
check_mlx_installed() {
    python3 -c "import mlx" 2>/dev/null
}

# Check CoreML tools availability
check_coreml_tools() {
    python3 -c "import coremltools" 2>/dev/null
}

# Check if a process is listening on a given port (macOS lsof)
_port_listening() {
    local port="$1"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

# Get Ollama model list (returns JSON or empty)
_ollama_models() {
    curl -sf --max-time 3 "${OLLAMA_URL}/api/tags" 2>/dev/null || echo ""
}

# Get mascarade providers
_mascarade_providers() {
    curl -sf --max-time 3 "${MASCARADE_CORE_URL}/v1/providers" 2>/dev/null || echo ""
}

# Get P2P mesh status
_p2p_status() {
    curl -sf --max-time 3 "${MASCARADE_CORE_URL}/v1/p2p/status" 2>/dev/null || echo ""
}

# =============================================================================
# 1. STATUS DASHBOARD
# =============================================================================

status_dashboard() {
    cls
    log_action "Opened status dashboard"
    echo -e "\n  ${MAGENTA}${BOLD}Apple Intelligence Status Dashboard${NC}"
    echo -e "  ${DIM}$(printf '═%.0s' $(seq 1 55))${NC}\n"

    local width=60

    # -- MLX-LM --
    box_header "MLX-LM Server" "$width"
    if check_mlx_lm_installed; then
        local mlx_ver
        mlx_ver="$(python3 -c 'import mlx_lm; print(mlx_lm.__version__)' 2>/dev/null || echo 'unknown')"
        box_row "$(echo -e "Package:  ${ICON_OK} installed (v${mlx_ver})")" "$width"
    else
        box_row "$(echo -e "Package:  ${ICON_ERR} not installed")" "$width"
    fi
    if _http_ok "${MLX_LM_URL}/health" 2 || _port_listening 8201; then
        box_row "$(echo -e "Server:   ${ICON_OK} running (${MLX_LM_URL})")" "$width"
    else
        box_row "$(echo -e "Server:   ${ICON_OFF} not running")" "$width"
    fi
    box_footer "$width"
    echo ""

    # -- Exo Cluster --
    box_header "Exo Distributed Inference" "$width"
    if _cmd_exists exo; then
        box_row "$(echo -e "CLI:      ${ICON_OK} installed")" "$width"
    else
        box_row "$(echo -e "CLI:      ${ICON_OFF} not found")" "$width"
    fi
    if _http_ok "${EXO_URL}/health" 2 || _port_listening 52415; then
        box_row "$(echo -e "Cluster:  ${ICON_OK} active")" "$width"
    else
        box_row "$(echo -e "Cluster:  ${ICON_OFF} not active")" "$width"
    fi
    box_footer "$width"
    echo ""

    # -- CoreML --
    box_header "CoreML / coremltools" "$width"
    if check_coreml_tools; then
        local cml_ver
        cml_ver="$(python3 -c 'import coremltools; print(coremltools.__version__)' 2>/dev/null || echo 'unknown')"
        box_row "$(echo -e "Tools:    ${ICON_OK} installed (v${cml_ver})")" "$width"
    else
        box_row "$(echo -e "Tools:    ${ICON_OFF} not installed")" "$width"
    fi
    if check_mlx_installed; then
        local mlx_ver
        mlx_ver="$(python3 -c 'import mlx.core; print(mlx.core.__version__)' 2>/dev/null || echo 'unknown')"
        box_row "$(echo -e "MLX:      ${ICON_OK} installed (v${mlx_ver})")" "$width"
    else
        box_row "$(echo -e "MLX:      ${ICON_OFF} not installed")" "$width"
    fi
    box_footer "$width"
    echo ""

    # -- Ollama --
    box_header "Ollama" "$width"
    if _cmd_exists ollama; then
        box_row "$(echo -e "Binary:   ${ICON_OK} installed")" "$width"
    else
        box_row "$(echo -e "Binary:   ${ICON_OFF} not found")" "$width"
    fi
    if _http_ok "${OLLAMA_URL}/api/tags" 2; then
        local model_count
        model_count="$(curl -sf --max-time 3 "${OLLAMA_URL}/api/tags" 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("models",[])))' 2>/dev/null || echo '?')"
        box_row "$(echo -e "Server:   ${ICON_OK} running (${model_count} models)")" "$width"
    else
        box_row "$(echo -e "Server:   ${ICON_OFF} not running")" "$width"
    fi
    box_footer "$width"
    echo ""

    # -- Mascarade Core --
    box_header "Mascarade Core API" "$width"
    if _http_ok "${MASCARADE_CORE_URL}/v1/health" 2; then
        box_row "$(echo -e "API:      ${ICON_OK} healthy (${MASCARADE_CORE_URL})")" "$width"
    else
        box_row "$(echo -e "API:      ${ICON_OFF} not reachable")" "$width"
    fi
    # P2P
    local p2p
    p2p="$(_p2p_status)"
    if [[ -n "$p2p" ]]; then
        local peers
        peers="$(echo "$p2p" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("peers",[])))' 2>/dev/null || echo '?')"
        box_row "$(echo -e "P2P Mesh: ${ICON_OK} ${peers} peers connected")" "$width"
    else
        box_row "$(echo -e "P2P Mesh: ${ICON_OFF} unavailable")" "$width"
    fi
    box_footer "$width"
    echo ""

    # -- System info --
    echo -e "  ${DIM}System: $(uname -m) | macOS $(sw_vers -productVersion 2>/dev/null || echo '?') | $(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f GB RAM", $1/1073741824}' || echo '? RAM') | $(sysctl -n hw.logicalcpu 2>/dev/null || echo '?') cores${NC}"

    press_any_key
}

# =============================================================================
# 2. MLX-LM MANAGEMENT
# =============================================================================

mlx_lm_menu() {
    while true; do
        cls
        log_action "Opened MLX-LM management menu"
        echo -e "\n  ${MAGENTA}${BOLD}MLX-LM Management${NC}"
        echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 40))${NC}\n"

        menu_item "1" "Install MLX-LM" "pip install mlx-lm (Apple Silicon only)"
        menu_item "2" "Start MLX-LM Server" "Launch local inference server on :8201"
        menu_item "3" "Stop MLX-LM Server" "Kill running MLX-LM server process"
        menu_item "4" "List Local Models" "Show MLX models in ${MODELS_ROOT}"
        menu_item "5" "Download Model" "Pull a model from HuggingFace for MLX"
        menu_item "6" "Run Quick Benchmark" "Measure tokens/sec on current model"
        menu_item "7" "Server Status" "Check MLX-LM server health"
        echo ""
        menu_item "b" "Back" "Return to main menu"

        local choice
        choice="$(prompt_choice "Select")"

        case "$choice" in
            1) _mlx_install ;;
            2) _mlx_start ;;
            3) _mlx_stop ;;
            4) _mlx_list_models ;;
            5) _mlx_download_model ;;
            6) _mlx_benchmark ;;
            7) _mlx_status ;;
            b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

_mlx_install() {
    cls
    section_header "Install MLX-LM"
    log_action "Installing MLX-LM"

    if check_mlx_lm_installed; then
        echo -e "  ${ICON_OK} mlx-lm is already installed"
        local ver
        ver="$(python3 -c 'import mlx_lm; print(mlx_lm.__version__)' 2>/dev/null || echo 'unknown')"
        echo -e "  ${DIM}Version: ${ver}${NC}"
    else
        echo -e "  ${ICON_ARROW} Installing mlx-lm via pip..."
        if python3 -m pip install --user mlx-lm 2>&1 | tail -5; then
            echo -e "\n  ${ICON_OK} mlx-lm installed successfully"
            log_info "MLX-LM installed successfully"
        else
            echo -e "\n  ${ICON_ERR} Installation failed"
            log_error "MLX-LM installation failed"
        fi
    fi
    press_any_key
}

_mlx_start() {
    cls
    section_header "Start MLX-LM Server"
    log_action "Starting MLX-LM server"

    if _port_listening 8201; then
        echo -e "  ${ICON_WARN} Port 8201 is already in use"
        echo -e "  ${DIM}A server may already be running${NC}"
        press_any_key
        return
    fi

    # Check if the run script exists
    local run_script="${REPO_DIR}/scripts/run_apple_llm_service.sh"
    if [[ -x "$run_script" ]]; then
        echo -e "  ${ICON_ARROW} Launching via ${DIM}run_apple_llm_service.sh${NC}..."
        echo -e "  ${DIM}Server will start in the background${NC}"
        nohup bash "$run_script" >> "${LOG_DIR}/mlx_lm_server.log" 2>&1 &
        local pid=$!
        echo -e "  ${ICON_OK} Server launched (PID: ${pid})"
        echo -e "  ${DIM}Logs: ${LOG_DIR}/mlx_lm_server.log${NC}"
        log_info "MLX-LM server started with PID ${pid}"
    else
        echo -e "  ${ICON_WARN} run_apple_llm_service.sh not found"
        echo -e "  ${DIM}Attempting direct mlx_lm.server launch...${NC}"
        if check_mlx_lm_installed; then
            echo -en "  Model name (e.g. mlx-community/Qwen2.5-0.5B-Instruct-4bit): "
            read -r model_name
            if [[ -n "$model_name" ]]; then
                nohup python3 -m mlx_lm.server --model "$model_name" --port 8201 >> "${LOG_DIR}/mlx_lm_server.log" 2>&1 &
                echo -e "  ${ICON_OK} Server launching with model ${model_name}"
                log_info "MLX-LM server started with model ${model_name}"
            fi
        else
            echo -e "  ${ICON_ERR} mlx-lm not installed. Install it first."
        fi
    fi
    press_any_key
}

_mlx_stop() {
    cls
    section_header "Stop MLX-LM Server"
    log_action "Stopping MLX-LM server"

    local pids
    pids="$(pgrep -f 'mlx_lm.server\|run_apple_llm_service' 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
        echo -e "  ${ICON_OFF} No MLX-LM server process found"
    else
        echo -e "  ${ICON_ARROW} Stopping processes: ${pids}"
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 1
        # Verify
        if pgrep -f 'mlx_lm.server\|run_apple_llm_service' >/dev/null 2>&1; then
            echo -e "  ${ICON_WARN} Processes still running, sending SIGKILL..."
            echo "$pids" | xargs kill -9 2>/dev/null || true
        fi
        echo -e "  ${ICON_OK} Server stopped"
        log_info "MLX-LM server stopped"
    fi
    press_any_key
}

_mlx_list_models() {
    cls
    section_header "Local MLX Models"
    log_action "Listing local MLX models"

    echo -e "  ${DIM}Models root: ${MODELS_ROOT}${NC}\n"

    if [[ -d "${MODELS_ROOT}" ]]; then
        local count=0
        while IFS= read -r -d '' dir; do
            local name
            name="$(basename "$dir")"
            local size
            size="$(du -sh "$dir" 2>/dev/null | cut -f1)"
            echo -e "  ${ICON_ARROW} ${BOLD}${name}${NC}  ${DIM}(${size})${NC}"
            count=$((count + 1))
        done < <(find "${MODELS_ROOT}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

        if (( count == 0 )); then
            echo -e "  ${DIM}No models found in ${MODELS_ROOT}${NC}"
        else
            echo -e "\n  ${DIM}Total: ${count} model(s)${NC}"
        fi
    else
        echo -e "  ${ICON_OFF} Models directory does not exist"
        echo -e "  ${DIM}Create it with: mkdir -p ${MODELS_ROOT}${NC}"
    fi

    # Also check HuggingFace cache for MLX models
    local hf_cache="${HOME}/.cache/huggingface/hub"
    if [[ -d "$hf_cache" ]]; then
        echo ""
        echo -e "  ${DIM}HuggingFace cache models with MLX:${NC}"
        local mlx_count=0
        while IFS= read -r line; do
            echo -e "    ${DIM}${line}${NC}"
            mlx_count=$((mlx_count + 1))
        done < <(ls -d "${hf_cache}"/models--*mlx* 2>/dev/null | sed 's|.*/models--|  |' | head -15)
        if (( mlx_count == 0 )); then
            echo -e "    ${DIM}(none)${NC}"
        fi
    fi

    press_any_key
}

_mlx_download_model() {
    cls
    section_header "Download MLX Model"
    log_action "Download MLX model"

    echo -e "  ${DIM}Popular MLX models:${NC}"
    echo -e "    1. mlx-community/Qwen2.5-0.5B-Instruct-4bit"
    echo -e "    2. mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
    echo -e "    3. mlx-community/Mistral-7B-Instruct-v0.3-4bit"
    echo -e "    4. mlx-community/Llama-3.2-3B-Instruct-4bit"
    echo -e "    5. Custom (enter HF repo)"
    echo ""
    echo -en "  ${CYAN}Select${NC} ${DIM}>${NC} "
    read -r model_choice

    local repo=""
    case "$model_choice" in
        1) repo="mlx-community/Qwen2.5-0.5B-Instruct-4bit" ;;
        2) repo="mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit" ;;
        3) repo="mlx-community/Mistral-7B-Instruct-v0.3-4bit" ;;
        4) repo="mlx-community/Llama-3.2-3B-Instruct-4bit" ;;
        5)
            echo -en "  HuggingFace repo: "
            read -r repo
            ;;
        *) return ;;
    esac

    if [[ -z "$repo" ]]; then
        echo -e "  ${ICON_WARN} No model selected"
        press_any_key
        return
    fi

    echo -e "\n  ${ICON_ARROW} Downloading ${BOLD}${repo}${NC}..."
    log_info "Downloading model ${repo}"

    if python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('${repo}', local_dir=None)
print('Download complete')
" 2>&1; then
        echo -e "\n  ${ICON_OK} Model downloaded successfully"
        log_info "Model ${repo} downloaded"
    else
        echo -e "\n  ${ICON_ERR} Download failed"
        log_error "Model download failed for ${repo}"
    fi

    press_any_key
}

_mlx_benchmark() {
    cls
    section_header "MLX-LM Quick Benchmark"
    log_action "Running MLX-LM benchmark"

    if ! check_mlx_lm_installed; then
        echo -e "  ${ICON_ERR} mlx-lm is not installed"
        press_any_key
        return
    fi

    echo -en "  Model (e.g. mlx-community/Qwen2.5-0.5B-Instruct-4bit): "
    read -r bench_model
    if [[ -z "$bench_model" ]]; then
        bench_model="mlx-community/Qwen2.5-0.5B-Instruct-4bit"
    fi

    echo -e "\n  ${ICON_ARROW} Running benchmark on ${BOLD}${bench_model}${NC}..."
    echo -e "  ${DIM}Prompt: 'Explain quantum computing in 3 sentences.'${NC}\n"

    local start_time end_time duration
    start_time=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')

    if python3 -c "
from mlx_lm import load, generate
model, tokenizer = load('${bench_model}')
prompt = 'Explain quantum computing in 3 sentences.'
messages = [{'role': 'user', 'content': prompt}]
text = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
response = generate(model, tokenizer, prompt=text, max_tokens=256, verbose=True)
" 2>&1; then
        end_time=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
        if [[ -n "$start_time" && -n "$end_time" ]]; then
            duration=$(( (end_time - start_time) / 1000000 ))
            echo -e "\n  ${ICON_OK} Benchmark complete in ${duration}ms"
            log_info "MLX-LM benchmark: ${bench_model} completed in ${duration}ms"
        fi
    else
        echo -e "\n  ${ICON_ERR} Benchmark failed"
        log_error "MLX-LM benchmark failed for ${bench_model}"
    fi

    press_any_key
}

_mlx_status() {
    cls
    section_header "MLX-LM Server Status"

    # Package check
    if check_mlx_lm_installed; then
        local ver
        ver="$(python3 -c 'import mlx_lm; print(mlx_lm.__version__)' 2>/dev/null || echo '?')"
        echo -e "  ${ICON_OK} mlx-lm package: v${ver}"
    else
        echo -e "  ${ICON_ERR} mlx-lm package: not installed"
    fi

    # Server process
    local pids
    pids="$(pgrep -f 'mlx_lm.server\|run_apple_llm_service' 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
        echo -e "  ${ICON_OK} Server process: running (PID: $(echo $pids | tr '\n' ','))"
    else
        echo -e "  ${ICON_OFF} Server process: not running"
    fi

    # HTTP check
    if _http_ok "${MLX_LM_URL}/health" 2; then
        echo -e "  ${ICON_OK} HTTP endpoint: responding"
        # Try to get model info
        local models_resp
        models_resp="$(curl -sf --max-time 3 "${MLX_LM_URL}/models" 2>/dev/null || curl -sf --max-time 3 "${MLX_LM_URL}/v1/models" 2>/dev/null || true)"
        if [[ -n "$models_resp" ]]; then
            echo -e "  ${ICON_ARROW} Models response:"
            echo "$models_resp" | python3 -m json.tool 2>/dev/null | head -15 | sed 's/^/    /'
        fi
    else
        echo -e "  ${ICON_OFF} HTTP endpoint: not responding"
    fi

    press_any_key
}

# =============================================================================
# 3. EXO CLUSTER
# =============================================================================

exo_menu() {
    while true; do
        cls
        log_action "Opened Exo cluster menu"
        echo -e "\n  ${MAGENTA}${BOLD}Exo Distributed Inference Cluster${NC}"
        echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 45))${NC}\n"

        menu_item "1" "Cluster Status" "Show connected nodes and topology"
        menu_item "2" "Start Exo Node" "Join or create an Exo cluster"
        menu_item "3" "Stop Exo Node" "Leave the cluster gracefully"
        menu_item "4" "Discover Peers" "Scan LAN for Exo-compatible nodes"
        menu_item "5" "Monitor Performance" "Show inference throughput per node"
        menu_item "6" "View Exo Config" "Display current Exo configuration"
        echo ""
        menu_item "b" "Back" "Return to main menu"

        local choice
        choice="$(prompt_choice "Select")"

        case "$choice" in
            1) _exo_status ;;
            2) _exo_start ;;
            3) _exo_stop ;;
            4) _exo_discover ;;
            5) _exo_monitor ;;
            6) _exo_config ;;
            b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

_exo_status() {
    cls
    section_header "Exo Cluster Status"
    log_action "Checking Exo cluster status"

    if ! _cmd_exists exo; then
        echo -e "  ${ICON_ERR} Exo CLI not found"
        echo -e "  ${DIM}Install with: pip install exo-inference${NC}"
        press_any_key
        return
    fi

    # Check if exo is running
    local pids
    pids="$(pgrep -f 'exo' 2>/dev/null | head -5 || true)"
    if [[ -n "$pids" ]]; then
        echo -e "  ${ICON_OK} Exo process(es) running"
        echo -e "  ${DIM}PIDs: $(echo $pids | tr '\n' ' ')${NC}"
    else
        echo -e "  ${ICON_OFF} No Exo processes running"
    fi

    # Check HTTP API
    if _http_ok "${EXO_URL}/health" 2; then
        echo -e "  ${ICON_OK} Exo API responding at ${EXO_URL}"

        # Try to get cluster topology
        local topology
        topology="$(curl -sf --max-time 5 "${EXO_URL}/topology" 2>/dev/null || true)"
        if [[ -n "$topology" ]]; then
            echo ""
            echo -e "  ${BOLD}Cluster Topology:${NC}"
            echo "$topology" | python3 -m json.tool 2>/dev/null | head -30 | sed 's/^/    /'
        fi
    else
        echo -e "  ${ICON_OFF} Exo API not responding at ${EXO_URL}"
    fi

    # Show Apple Silicon capabilities
    echo ""
    echo -e "  ${BOLD}Local Node Capabilities:${NC}"
    local chip
    chip="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'unknown')"
    local mem
    mem="$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1073741824}' || echo '?')"
    local cores
    cores="$(sysctl -n hw.logicalcpu 2>/dev/null || echo '?')"
    echo -e "  ${DIM}Chip:   ${chip}${NC}"
    echo -e "  ${DIM}Memory: ${mem} GB unified${NC}"
    echo -e "  ${DIM}Cores:  ${cores} logical${NC}"

    press_any_key
}

_exo_start() {
    cls
    section_header "Start Exo Node"
    log_action "Starting Exo node"

    if ! _cmd_exists exo; then
        echo -e "  ${ICON_ERR} Exo not installed"
        echo -e "  ${DIM}Install: pip install exo-inference${NC}"
        press_any_key
        return
    fi

    if pgrep -f 'exo' >/dev/null 2>&1; then
        echo -e "  ${ICON_WARN} Exo is already running"
        press_any_key
        return
    fi

    echo -e "  ${DIM}Start mode:${NC}"
    echo -e "    1. Create new cluster"
    echo -e "    2. Join existing cluster"
    echo ""
    echo -en "  ${CYAN}Select${NC} ${DIM}>${NC} "
    read -r start_mode

    case "$start_mode" in
        1)
            echo -e "\n  ${ICON_ARROW} Starting new Exo cluster..."
            nohup exo run --port 52415 >> "${LOG_DIR}/exo_cluster.log" 2>&1 &
            echo -e "  ${ICON_OK} Exo cluster started (PID: $!)"
            log_info "Exo cluster started, PID $!"
            ;;
        2)
            echo -en "  Peer address (host:port): "
            read -r peer_addr
            if [[ -n "$peer_addr" ]]; then
                echo -e "\n  ${ICON_ARROW} Joining cluster at ${peer_addr}..."
                nohup exo run --port 52415 --peer "$peer_addr" >> "${LOG_DIR}/exo_cluster.log" 2>&1 &
                echo -e "  ${ICON_OK} Joined cluster (PID: $!)"
                log_info "Exo joined cluster at ${peer_addr}, PID $!"
            fi
            ;;
        *)
            return
            ;;
    esac

    press_any_key
}

_exo_stop() {
    cls
    section_header "Stop Exo Node"
    log_action "Stopping Exo node"

    local pids
    pids="$(pgrep -f 'exo' 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
        echo -e "  ${ICON_OFF} No Exo processes found"
    else
        echo -e "  ${ICON_ARROW} Stopping Exo processes: ${pids}"
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 1
        echo -e "  ${ICON_OK} Exo stopped"
        log_info "Exo stopped"
    fi
    press_any_key
}

_exo_discover() {
    cls
    section_header "Discover Exo Peers"
    log_action "Discovering Exo peers"

    echo -e "  ${ICON_ARROW} Scanning local network for Exo nodes..."
    echo ""

    # Use mDNS / Bonjour to find exo services (macOS)
    if _cmd_exists dns-sd; then
        echo -e "  ${DIM}Using Bonjour/mDNS discovery (5s scan)...${NC}"
        timeout 5 dns-sd -B _exo._tcp 2>/dev/null | head -20 || echo -e "  ${DIM}No Exo mDNS services found${NC}"
    fi

    # Also check common ports on LAN
    echo ""
    echo -e "  ${DIM}Probing known hosts for Exo API (port 52415)...${NC}"
    local hosts=("192.168.0.119" "192.168.0.120" "192.168.0.210" "localhost")
    for host in "${hosts[@]}"; do
        if curl -sf --max-time 2 "http://${host}:52415/health" >/dev/null 2>&1; then
            echo -e "  ${ICON_OK} ${host}:52415 — Exo node found"
        else
            echo -e "  ${ICON_OFF} ${host}:52415 — no response"
        fi
    done

    press_any_key
}

_exo_monitor() {
    cls
    section_header "Exo Performance Monitor"

    if ! _http_ok "${EXO_URL}/health" 2; then
        echo -e "  ${ICON_OFF} Exo cluster not running"
        press_any_key
        return
    fi

    echo -e "  ${DIM}Fetching metrics from ${EXO_URL}...${NC}\n"

    local metrics
    metrics="$(curl -sf --max-time 5 "${EXO_URL}/metrics" 2>/dev/null || true)"
    if [[ -n "$metrics" ]]; then
        echo "$metrics" | python3 -m json.tool 2>/dev/null | head -40 | sed 's/^/    /' || echo "$metrics" | head -40 | sed 's/^/    /'
    else
        echo -e "  ${DIM}No metrics endpoint available${NC}"
        echo -e "  ${DIM}Try: curl ${EXO_URL}/metrics${NC}"
    fi

    press_any_key
}

_exo_config() {
    cls
    section_header "Exo Configuration"

    echo -e "  ${BOLD}Current Settings:${NC}"
    echo -e "  ${DIM}Exo URL:      ${EXO_URL}${NC}"
    echo -e "  ${DIM}Models Root:  ${MODELS_ROOT}${NC}"
    echo ""

    # Check for exo config files
    local exo_config_paths=(
        "${HOME}/.exo/config.yaml"
        "${HOME}/.exo/config.json"
        "${HOME}/.config/exo/config.yaml"
    )
    local found=false
    for cfg in "${exo_config_paths[@]}"; do
        if [[ -f "$cfg" ]]; then
            echo -e "  ${ICON_OK} Config file: ${cfg}"
            echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 40))${NC}"
            head -30 "$cfg" | sed 's/^/    /'
            found=true
            break
        fi
    done
    if [[ "$found" == false ]]; then
        echo -e "  ${ICON_OFF} No Exo config file found"
        echo -e "  ${DIM}Exo uses default settings${NC}"
    fi

    press_any_key
}

# =============================================================================
# 4. MODEL REGISTRY
# =============================================================================

model_registry_menu() {
    while true; do
        cls
        log_action "Opened model registry menu"
        echo -e "\n  ${MAGENTA}${BOLD}Model Registry${NC}"
        echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 40))${NC}\n"

        menu_item "1" "List All Models" "Show models from all sources"
        menu_item "2" "Convert HF to MLX" "Convert HuggingFace model to MLX format"
        menu_item "3" "Convert MLX to GGUF" "Export MLX model to GGUF for Ollama"
        menu_item "4" "Quantize Model" "Apply quantization (4-bit, 8-bit)"
        menu_item "5" "Deploy to Ollama" "Register GGUF model with Ollama"
        menu_item "6" "CoreML Conversion" "Convert model to CoreML format"
        menu_item "7" "Model Info" "Show details for a specific model"
        echo ""
        menu_item "b" "Back" "Return to main menu"

        local choice
        choice="$(prompt_choice "Select")"

        case "$choice" in
            1) _registry_list_all ;;
            2) _registry_hf_to_mlx ;;
            3) _registry_mlx_to_gguf ;;
            4) _registry_quantize ;;
            5) _registry_deploy_ollama ;;
            6) _registry_coreml ;;
            7) _registry_model_info ;;
            b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

_registry_list_all() {
    cls
    section_header "All Available Models"
    log_action "Listing all models"

    local total=0

    # Local MLX models
    echo -e "\n  ${BOLD}${CYAN}Local MLX Models (${MODELS_ROOT}):${NC}"
    if [[ -d "${MODELS_ROOT}" ]]; then
        while IFS= read -r -d '' dir; do
            local name size
            name="$(basename "$dir")"
            size="$(du -sh "$dir" 2>/dev/null | cut -f1)"
            echo -e "    ${ICON_ARROW} ${name}  ${DIM}(${size})${NC}"
            total=$((total + 1))
        done < <(find "${MODELS_ROOT}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    else
        echo -e "    ${DIM}(directory not found)${NC}"
    fi

    # Ollama models
    echo -e "\n  ${BOLD}${CYAN}Ollama Models:${NC}"
    local ollama_resp
    ollama_resp="$(_ollama_models)"
    if [[ -n "$ollama_resp" ]]; then
        echo "$ollama_resp" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    for m in models:
        name = m.get('name', '?')
        size_gb = m.get('size', 0) / 1e9
        modified = m.get('modified_at', '?')[:19]
        print(f'    ▸ {name}  ({size_gb:.1f} GB)  [{modified}]')
except Exception:
    print('    (parse error)')
" 2>/dev/null || echo -e "    ${DIM}(parse error)${NC}"
    else
        echo -e "    ${DIM}(Ollama not running)${NC}"
    fi

    # HuggingFace cache
    echo -e "\n  ${BOLD}${CYAN}HuggingFace Cache:${NC}"
    local hf_cache="${HOME}/.cache/huggingface/hub"
    if [[ -d "$hf_cache" ]]; then
        local hf_count=0
        while IFS= read -r dir; do
            local name size
            name="$(basename "$dir" | sed 's/^models--//' | tr '--' '/')"
            size="$(du -sh "$dir" 2>/dev/null | cut -f1)"
            echo -e "    ${ICON_ARROW} ${name}  ${DIM}(${size})${NC}"
            hf_count=$((hf_count + 1))
            total=$((total + 1))
        done < <(ls -d "${hf_cache}"/models--* 2>/dev/null | head -20)
        if (( hf_count == 0 )); then
            echo -e "    ${DIM}(no cached models)${NC}"
        fi
    else
        echo -e "    ${DIM}(no HF cache)${NC}"
    fi

    echo -e "\n  ${DIM}Total indexed: ${total} model(s)${NC}"
    press_any_key
}

_registry_hf_to_mlx() {
    cls
    section_header "Convert HuggingFace Model to MLX"
    log_action "HF to MLX conversion"

    if ! check_mlx_lm_installed; then
        echo -e "  ${ICON_ERR} mlx-lm required for conversion"
        press_any_key
        return
    fi

    echo -en "  HF model repo (e.g. Qwen/Qwen2.5-0.5B-Instruct): "
    read -r hf_repo
    [[ -z "$hf_repo" ]] && return

    echo -en "  Quantization bits [4]: "
    read -r quant_bits
    quant_bits="${quant_bits:-4}"

    local output_name
    output_name="$(echo "$hf_repo" | tr '/' '-')-${quant_bits}bit-mlx"
    local output_path="${MODELS_ROOT}/${output_name}"

    echo -e "\n  ${ICON_ARROW} Converting ${BOLD}${hf_repo}${NC} to MLX (${quant_bits}-bit)..."
    echo -e "  ${DIM}Output: ${output_path}${NC}\n"

    mkdir -p "${MODELS_ROOT}"
    if python3 -m mlx_lm.convert \
        --hf-path "$hf_repo" \
        --mlx-path "$output_path" \
        -q --q-bits "$quant_bits" 2>&1; then
        echo -e "\n  ${ICON_OK} Conversion complete: ${output_path}"
        log_info "Converted ${hf_repo} to MLX at ${output_path}"
    else
        echo -e "\n  ${ICON_ERR} Conversion failed"
        log_error "HF to MLX conversion failed for ${hf_repo}"
    fi

    press_any_key
}

_registry_mlx_to_gguf() {
    cls
    section_header "Convert MLX Model to GGUF"
    log_action "MLX to GGUF conversion"

    echo -en "  MLX model path: "
    read -r mlx_path
    [[ -z "$mlx_path" ]] && return

    echo -en "  Output GGUF path [auto]: "
    read -r gguf_path
    if [[ -z "$gguf_path" ]]; then
        gguf_path="${mlx_path}.gguf"
    fi

    echo -e "\n  ${ICON_ARROW} Converting to GGUF..."
    echo -e "  ${DIM}This requires llama.cpp convert tools${NC}\n"

    # Check for llama.cpp convert script
    local convert_script=""
    for candidate in \
        "$(brew --prefix 2>/dev/null)/bin/llama-convert" \
        "${HOME}/llama.cpp/convert_hf_to_gguf.py" \
        "${HOME}/llama.cpp/convert.py"; do
        if [[ -f "$candidate" ]]; then
            convert_script="$candidate"
            break
        fi
    done

    if [[ -n "$convert_script" ]]; then
        echo -e "  ${ICON_ARROW} Using: ${convert_script}"
        if python3 "$convert_script" "$mlx_path" --outfile "$gguf_path" --outtype f16 2>&1; then
            echo -e "\n  ${ICON_OK} GGUF created: ${gguf_path}"
            log_info "MLX to GGUF conversion done: ${gguf_path}"
        else
            echo -e "\n  ${ICON_ERR} Conversion failed"
            log_error "MLX to GGUF conversion failed"
        fi
    else
        echo -e "  ${ICON_ERR} llama.cpp convert tools not found"
        echo -e "  ${DIM}Install: brew install llama.cpp  OR  git clone https://github.com/ggml-org/llama.cpp${NC}"
    fi

    press_any_key
}

_registry_quantize() {
    cls
    section_header "Quantize Model"
    log_action "Quantize model"

    echo -e "  ${BOLD}Quantization Methods:${NC}"
    echo -e "    1. MLX quantization (4-bit, 8-bit)"
    echo -e "    2. GGUF quantization (Q4_K_M, Q5_K_M, Q8_0)"
    echo ""
    echo -en "  ${CYAN}Select method${NC} ${DIM}>${NC} "
    read -r quant_method

    case "$quant_method" in
        1)
            echo -en "  Source HF model repo: "
            read -r src_repo
            [[ -z "$src_repo" ]] && return

            echo -en "  Bits (4 or 8) [4]: "
            read -r bits
            bits="${bits:-4}"

            local out_name
            out_name="$(echo "$src_repo" | tr '/' '-')-${bits}bit-mlx"

            echo -e "\n  ${ICON_ARROW} Quantizing to ${bits}-bit MLX..."
            mkdir -p "${MODELS_ROOT}"
            python3 -m mlx_lm.convert \
                --hf-path "$src_repo" \
                --mlx-path "${MODELS_ROOT}/${out_name}" \
                -q --q-bits "$bits" 2>&1 || true
            ;;
        2)
            echo -en "  Source GGUF file: "
            read -r src_gguf
            [[ -z "$src_gguf" ]] && return

            echo -e "  ${DIM}Available: Q4_0, Q4_K_M, Q5_K_M, Q8_0, F16${NC}"
            echo -en "  Quantization type [Q4_K_M]: "
            read -r quant_type
            quant_type="${quant_type:-Q4_K_M}"

            local out_gguf="${src_gguf%.gguf}-${quant_type}.gguf"
            echo -e "\n  ${ICON_ARROW} Quantizing to ${quant_type}..."

            local quantize_bin=""
            for candidate in \
                "$(brew --prefix 2>/dev/null)/bin/llama-quantize" \
                "${HOME}/llama.cpp/build/bin/llama-quantize" \
                "${HOME}/llama.cpp/quantize"; do
                if [[ -x "$candidate" ]]; then
                    quantize_bin="$candidate"
                    break
                fi
            done

            if [[ -n "$quantize_bin" ]]; then
                "$quantize_bin" "$src_gguf" "$out_gguf" "$quant_type" 2>&1 || true
            else
                echo -e "  ${ICON_ERR} llama-quantize binary not found"
            fi
            ;;
        *)
            return
            ;;
    esac

    press_any_key
}

_registry_deploy_ollama() {
    cls
    section_header "Deploy Model to Ollama"
    log_action "Deploy to Ollama"

    if ! _cmd_exists ollama; then
        echo -e "  ${ICON_ERR} Ollama not installed"
        press_any_key
        return
    fi

    echo -en "  GGUF file path: "
    read -r gguf_file
    [[ -z "$gguf_file" ]] && return
    if [[ ! -f "$gguf_file" ]]; then
        echo -e "  ${ICON_ERR} File not found: ${gguf_file}"
        press_any_key
        return
    fi

    echo -en "  Model name in Ollama (e.g. mascarade-coder): "
    read -r ollama_name
    [[ -z "$ollama_name" ]] && return

    # Create a Modelfile
    local modelfile
    modelfile="$(mktemp /tmp/Modelfile.XXXXXX)"
    cat > "$modelfile" <<EOF
FROM ${gguf_file}

PARAMETER temperature 0.7
PARAMETER num_ctx 4096
EOF

    echo -e "\n  ${ICON_ARROW} Creating Ollama model ${BOLD}${ollama_name}${NC}..."
    if ollama create "$ollama_name" -f "$modelfile" 2>&1; then
        echo -e "\n  ${ICON_OK} Model '${ollama_name}' registered in Ollama"
        log_info "Deployed ${gguf_file} as ${ollama_name} to Ollama"
    else
        echo -e "\n  ${ICON_ERR} Deployment failed"
        log_error "Ollama deployment failed for ${ollama_name}"
    fi

    rm -f "$modelfile"
    press_any_key
}

_registry_coreml() {
    cls
    section_header "CoreML Model Conversion"
    log_action "CoreML conversion"

    if ! check_coreml_tools; then
        echo -e "  ${ICON_ERR} coremltools not installed"
        echo -e "  ${DIM}Install: pip install coremltools${NC}"
        press_any_key
        return
    fi

    echo -e "  ${DIM}Use the install_apple_coreml_model.sh script for pre-built CoreML models.${NC}"
    echo -e "  ${DIM}This converts a HuggingFace model to CoreML .mlpackage format.${NC}\n"

    echo -en "  HF model repo: "
    read -r hf_repo
    [[ -z "$hf_repo" ]] && return

    echo -e "\n  ${ICON_ARROW} Converting ${hf_repo} to CoreML..."
    echo -e "  ${DIM}This may take a while for large models.${NC}\n"

    # Delegate to install script if available
    local install_script="${REPO_DIR}/scripts/install_apple_coreml_model.sh"
    if [[ -x "$install_script" ]]; then
        bash "$install_script" --repo "$hf_repo" 2>&1 | tail -20
    else
        echo -e "  ${ICON_WARN} install_apple_coreml_model.sh not found"
        echo -e "  ${DIM}Manual conversion via coremltools required${NC}"
    fi

    press_any_key
}

_registry_model_info() {
    cls
    section_header "Model Info"

    echo -en "  Model path or HF repo: "
    read -r model_ref
    [[ -z "$model_ref" ]] && return

    echo ""
    # If it's a local path
    if [[ -d "$model_ref" ]]; then
        echo -e "  ${BOLD}Local Model:${NC} ${model_ref}"
        echo -e "  ${DIM}Size: $(du -sh "$model_ref" 2>/dev/null | cut -f1)${NC}"
        echo ""
        echo -e "  ${BOLD}Contents:${NC}"
        ls -la "$model_ref" 2>/dev/null | head -20 | sed 's/^/    /'

        # Check for config.json
        if [[ -f "${model_ref}/config.json" ]]; then
            echo ""
            echo -e "  ${BOLD}config.json:${NC}"
            python3 -m json.tool "${model_ref}/config.json" 2>/dev/null | head -25 | sed 's/^/    /'
        fi
    else
        # Try HuggingFace
        echo -e "  ${ICON_ARROW} Fetching info from HuggingFace for ${BOLD}${model_ref}${NC}..."
        python3 -c "
from huggingface_hub import model_info
try:
    info = model_info('${model_ref}')
    print(f'  Model:      {info.modelId}')
    print(f'  Pipeline:   {info.pipeline_tag or \"N/A\"}')
    print(f'  Downloads:  {info.downloads:,}')
    print(f'  Likes:      {info.likes:,}')
    print(f'  Tags:       {', '.join(info.tags[:10])}')
    print(f'  Library:    {info.library_name or \"N/A\"}')
    if info.safetensors:
        total = sum(info.safetensors.get('total', {}).values()) if isinstance(info.safetensors.get('total'), dict) else 0
        print(f'  Parameters: {total:,}')
except Exception as e:
    print(f'  Error: {e}')
" 2>&1
    fi

    press_any_key
}

# =============================================================================
# 5. BENCHMARK SUITE
# =============================================================================

benchmark_menu() {
    while true; do
        cls
        log_action "Opened benchmark menu"
        echo -e "\n  ${MAGENTA}${BOLD}Benchmark Suite${NC}"
        echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 40))${NC}\n"

        menu_item "1" "MLX-LM Inference" "Benchmark local MLX model inference speed"
        menu_item "2" "Ollama Inference" "Benchmark Ollama model responses"
        menu_item "3" "Compare Providers" "Side-by-side provider comparison"
        menu_item "4" "Memory Usage" "Profile memory during inference"
        menu_item "5" "Generate Report" "Save benchmark results to file"
        echo ""
        menu_item "b" "Back" "Return to main menu"

        local choice
        choice="$(prompt_choice "Select")"

        case "$choice" in
            1) _bench_mlx ;;
            2) _bench_ollama ;;
            3) _bench_compare ;;
            4) _bench_memory ;;
            5) _bench_report ;;
            b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

_bench_mlx() {
    cls
    section_header "MLX-LM Inference Benchmark"
    log_action "Running MLX-LM benchmark"

    if ! check_mlx_lm_installed; then
        echo -e "  ${ICON_ERR} mlx-lm not installed"
        press_any_key
        return
    fi

    echo -en "  Model (HF repo or local path): "
    read -r model
    [[ -z "$model" ]] && model="mlx-community/Qwen2.5-0.5B-Instruct-4bit"

    local prompts=(
        "What is 2+2?"
        "Explain quantum computing in one sentence."
        "Write a Python function to sort a list."
    )

    echo -e "\n  ${ICON_ARROW} Benchmarking ${BOLD}${model}${NC} with ${#prompts[@]} prompts...\n"

    python3 -c "
import time, json
try:
    from mlx_lm import load, generate
    model, tokenizer = load('${model}')

    prompts = $(python3 -c "import json; print(json.dumps([
        'What is 2+2?',
        'Explain quantum computing in one sentence.',
        'Write a Python function to sort a list.'
    ]))")

    results = []
    for prompt in prompts:
        messages = [{'role': 'user', 'content': prompt}]
        text = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        start = time.perf_counter()
        resp = generate(model, tokenizer, prompt=text, max_tokens=128, verbose=False)
        elapsed = time.perf_counter() - start
        tok_count = len(tokenizer.encode(resp))
        tps = tok_count / elapsed if elapsed > 0 else 0
        results.append({'prompt': prompt[:40], 'tokens': tok_count, 'time_s': round(elapsed, 2), 'tok_per_s': round(tps, 1)})
        print(f'  Prompt: {prompt[:40]}...')
        print(f'    Tokens: {tok_count}, Time: {elapsed:.2f}s, Speed: {tps:.1f} tok/s')
        print()

    avg_tps = sum(r['tok_per_s'] for r in results) / len(results)
    print(f'  Average: {avg_tps:.1f} tokens/second')
except Exception as e:
    print(f'  Error: {e}')
" 2>&1

    press_any_key
}

_bench_ollama() {
    cls
    section_header "Ollama Inference Benchmark"
    log_action "Running Ollama benchmark"

    if ! _http_ok "${OLLAMA_URL}/api/tags" 2; then
        echo -e "  ${ICON_ERR} Ollama not running"
        press_any_key
        return
    fi

    # Get available models
    echo -e "  ${DIM}Available Ollama models:${NC}"
    local models_json
    models_json="$(curl -sf --max-time 5 "${OLLAMA_URL}/api/tags")"
    echo "$models_json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for i, m in enumerate(data.get('models', []), 1):
    print(f'    {i}. {m[\"name\"]}')
" 2>/dev/null

    echo ""
    echo -en "  Model name: "
    read -r ollama_model
    [[ -z "$ollama_model" ]] && return

    echo -e "\n  ${ICON_ARROW} Benchmarking ${BOLD}${ollama_model}${NC}...\n"

    local prompt="Explain the theory of relativity in 3 sentences."
    local start_time
    start_time="$(python3 -c 'import time; print(time.perf_counter())')"

    local resp
    resp="$(curl -sf --max-time 60 "${OLLAMA_URL}/api/generate" \
        -d "{\"model\":\"${ollama_model}\",\"prompt\":\"${prompt}\",\"stream\":false}" 2>/dev/null || true)"

    local end_time
    end_time="$(python3 -c 'import time; print(time.perf_counter())')"

    if [[ -n "$resp" ]]; then
        python3 -c "
import json
resp = json.loads('''${resp}''')
total_dur = resp.get('total_duration', 0) / 1e9
eval_count = resp.get('eval_count', 0)
eval_dur = resp.get('eval_duration', 0) / 1e9
prompt_eval = resp.get('prompt_eval_duration', 0) / 1e9
tps = eval_count / eval_dur if eval_dur > 0 else 0
print(f'  Total duration:    {total_dur:.2f}s')
print(f'  Prompt eval:       {prompt_eval:.2f}s')
print(f'  Generation:        {eval_dur:.2f}s')
print(f'  Tokens generated:  {eval_count}')
print(f'  Speed:             {tps:.1f} tokens/sec')
" 2>/dev/null || echo -e "  ${DIM}Could not parse response${NC}"
    else
        echo -e "  ${ICON_ERR} No response from Ollama"
    fi

    press_any_key
}

_bench_compare() {
    cls
    section_header "Provider Comparison"
    log_action "Running provider comparison benchmark"

    local prompt="Write a hello world program in Python."
    echo -e "  ${DIM}Prompt: '${prompt}'${NC}"
    echo -e "  ${DIM}Testing available providers...${NC}\n"

    local width=65
    printf "  ${BOLD}%-20s %-12s %-12s %-12s${NC}\n" "Provider" "Status" "Latency" "Tokens/s"
    echo -e "  $(printf '─%.0s' $(seq 1 $((width - 4))))"

    # MLX-LM
    if _http_ok "${MLX_LM_URL}/health" 2; then
        local mlx_start mlx_end mlx_latency
        mlx_start="$(python3 -c 'import time; print(time.perf_counter())')"
        local mlx_resp
        mlx_resp="$(curl -sf --max-time 30 "${MLX_LM_URL}/v1/chat/completions" \
            -H 'Content-Type: application/json' \
            -d "{\"messages\":[{\"role\":\"user\",\"content\":\"${prompt}\"}],\"max_tokens\":64}" 2>/dev/null || true)"
        mlx_end="$(python3 -c 'import time; print(time.perf_counter())')"
        mlx_latency="$(python3 -c "print(f'{${mlx_end}-${mlx_start}:.2f}s')")"
        if [[ -n "$mlx_resp" ]]; then
            printf "  ${GREEN}%-20s${NC} %-12s %-12s %-12s\n" "MLX-LM" "online" "$mlx_latency" "-"
        else
            printf "  ${YELLOW}%-20s${NC} %-12s %-12s %-12s\n" "MLX-LM" "error" "-" "-"
        fi
    else
        printf "  ${GRAY}%-20s${NC} %-12s %-12s %-12s\n" "MLX-LM" "offline" "-" "-"
    fi

    # Ollama
    if _http_ok "${OLLAMA_URL}/api/tags" 2; then
        local first_model
        first_model="$(curl -sf "${OLLAMA_URL}/api/tags" | python3 -c 'import json,sys; m=json.load(sys.stdin).get("models",[]); print(m[0]["name"] if m else "")' 2>/dev/null || true)"
        if [[ -n "$first_model" ]]; then
            local oll_start
            oll_start="$(python3 -c 'import time; print(time.perf_counter())')"
            local oll_resp
            oll_resp="$(curl -sf --max-time 60 "${OLLAMA_URL}/api/generate" \
                -d "{\"model\":\"${first_model}\",\"prompt\":\"${prompt}\",\"stream\":false}" 2>/dev/null || true)"
            local oll_end
            oll_end="$(python3 -c 'import time; print(time.perf_counter())')"
            local oll_latency
            oll_latency="$(python3 -c "print(f'{${oll_end}-${oll_start}:.2f}s')")"
            if [[ -n "$oll_resp" ]]; then
                local oll_tps
                oll_tps="$(echo "$oll_resp" | python3 -c 'import json,sys; r=json.load(sys.stdin); d=r.get("eval_duration",1)/1e9; c=r.get("eval_count",0); print(f"{c/d:.1f}" if d>0 else "-")' 2>/dev/null || echo '-')"
                printf "  ${GREEN}%-20s${NC} %-12s %-12s %-12s\n" "Ollama(${first_model})" "online" "$oll_latency" "$oll_tps"
            else
                printf "  ${YELLOW}%-20s${NC} %-12s %-12s %-12s\n" "Ollama" "error" "-" "-"
            fi
        else
            printf "  ${YELLOW}%-20s${NC} %-12s %-12s %-12s\n" "Ollama" "no models" "-" "-"
        fi
    else
        printf "  ${GRAY}%-20s${NC} %-12s %-12s %-12s\n" "Ollama" "offline" "-" "-"
    fi

    # Mascarade Core
    if _http_ok "${MASCARADE_CORE_URL}/v1/health" 2; then
        local mc_start
        mc_start="$(python3 -c 'import time; print(time.perf_counter())')"
        local mc_resp
        mc_resp="$(curl -sf --max-time 30 "${MASCARADE_CORE_URL}/v1/send" \
            -H 'Content-Type: application/json' \
            -H "Authorization: Bearer ${MASCARADE_API_KEY:-}" \
            -d "{\"messages\":[{\"role\":\"user\",\"content\":\"${prompt}\"}],\"max_tokens\":64}" 2>/dev/null || true)"
        local mc_end
        mc_end="$(python3 -c 'import time; print(time.perf_counter())')"
        local mc_latency
        mc_latency="$(python3 -c "print(f'{${mc_end}-${mc_start}:.2f}s')")"
        if [[ -n "$mc_resp" ]]; then
            printf "  ${GREEN}%-20s${NC} %-12s %-12s %-12s\n" "Mascarade Core" "online" "$mc_latency" "-"
        else
            printf "  ${YELLOW}%-20s${NC} %-12s %-12s %-12s\n" "Mascarade Core" "error" "-" "-"
        fi
    else
        printf "  ${GRAY}%-20s${NC} %-12s %-12s %-12s\n" "Mascarade Core" "offline" "-" "-"
    fi

    # Exo
    if _http_ok "${EXO_URL}/health" 2; then
        printf "  ${GREEN}%-20s${NC} %-12s %-12s %-12s\n" "Exo Cluster" "online" "-" "-"
    else
        printf "  ${GRAY}%-20s${NC} %-12s %-12s %-12s\n" "Exo Cluster" "offline" "-" "-"
    fi

    echo ""
    press_any_key
}

_bench_memory() {
    cls
    section_header "Memory Usage Profile"

    echo -e "  ${BOLD}System Memory:${NC}"
    local total_mem
    total_mem="$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.1f", $1/1073741824}' || echo '?')"
    echo -e "  ${DIM}Total:     ${total_mem} GB${NC}"

    # Get memory pressure
    local mem_pressure
    mem_pressure="$(memory_pressure 2>/dev/null | head -1 || echo 'unavailable')"
    echo -e "  ${DIM}Pressure:  ${mem_pressure}${NC}"

    # Check model-related processes
    echo -e "\n  ${BOLD}Model Process Memory:${NC}"

    local procs=("mlx_lm" "ollama" "exo" "python.*mascarade")
    for proc_pattern in "${procs[@]}"; do
        local proc_info
        proc_info="$(ps aux 2>/dev/null | grep -i "$proc_pattern" | grep -v grep | awk '{sum+=$6; count++} END {if(count>0) printf "%.1f MB (%d processes)", sum/1024, count; else print "not running"}' 2>/dev/null || echo 'check failed')"
        local label
        label="$(echo "$proc_pattern" | sed 's/\.\*//' | sed 's/\\//g')"
        echo -e "  ${DIM}${label}: ${proc_info}${NC}"
    done

    # Top memory consumers
    echo -e "\n  ${BOLD}Top Memory Consumers:${NC}"
    ps aux 2>/dev/null | sort -rn -k 6 | head -8 | awk '{printf "    %-30s %8.1f MB\n", $11, $6/1024}' 2>/dev/null || echo -e "  ${DIM}(unavailable)${NC}"

    press_any_key
}

_bench_report() {
    cls
    section_header "Generate Benchmark Report"
    log_action "Generating benchmark report"

    local report_file="${LOG_DIR}/benchmark_report_$(date '+%Y%m%d_%H%M%S').txt"

    {
        echo "============================================"
        echo "Mascarade Apple Intelligence Benchmark Report"
        echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Host: $(hostname)"
        echo "System: $(uname -m) | macOS $(sw_vers -productVersion 2>/dev/null || echo '?')"
        echo "Memory: $(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f GB", $1/1073741824}' || echo '?')"
        echo "CPU: $(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo '?')"
        echo "============================================"
        echo ""

        echo "--- Component Status ---"
        echo "MLX-LM installed: $(check_mlx_lm_installed && echo 'yes' || echo 'no')"
        echo "MLX installed: $(check_mlx_installed && echo 'yes' || echo 'no')"
        echo "CoreML tools: $(check_coreml_tools && echo 'yes' || echo 'no')"
        echo "Ollama: $(_cmd_exists ollama && echo 'installed' || echo 'not found')"
        echo "Ollama server: $(_http_ok "${OLLAMA_URL}/api/tags" 2 && echo 'running' || echo 'not running')"
        echo "Mascarade Core: $(_http_ok "${MASCARADE_CORE_URL}/v1/health" 2 && echo 'healthy' || echo 'not reachable')"
        echo "Exo CLI: $(_cmd_exists exo && echo 'installed' || echo 'not found')"
        echo ""

        echo "--- Ollama Models ---"
        curl -sf --max-time 5 "${OLLAMA_URL}/api/tags" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "(not available)"
        echo ""

        echo "--- Local Models ---"
        ls -la "${MODELS_ROOT}" 2>/dev/null || echo "(no models directory)"
        echo ""

        echo "--- Memory ---"
        vm_stat 2>/dev/null | head -10 || true
        echo ""
        echo "============================================"
    } > "$report_file" 2>&1

    echo -e "  ${ICON_OK} Report saved to: ${report_file}"
    echo -e "  ${DIM}$(wc -l < "$report_file") lines${NC}"
    log_info "Benchmark report saved to ${report_file}"

    press_any_key
}

# =============================================================================
# 6. LOGS
# =============================================================================

logs_menu() {
    while true; do
        cls
        log_action "Opened logs menu"
        echo -e "\n  ${MAGENTA}${BOLD}Log Management${NC}"
        echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 40))${NC}\n"

        menu_item "1" "View TUI Log" "Show apple_intelligence_tui.log"
        menu_item "2" "View MLX-LM Log" "Show MLX-LM server log"
        menu_item "3" "View Exo Log" "Show Exo cluster log"
        menu_item "4" "Log Analysis" "Error/warning/action counts"
        menu_item "5" "Clean Old Logs" "Remove rotated log files"
        menu_item "6" "List All Logs" "Show all log files with sizes"
        echo ""
        menu_item "b" "Back" "Return to main menu"

        local choice
        choice="$(prompt_choice "Select")"

        case "$choice" in
            1) _logs_view "${LOG_FILE}" "TUI Log" ;;
            2) _logs_view "${LOG_DIR}/mlx_lm_server.log" "MLX-LM Server Log" ;;
            3) _logs_view "${LOG_DIR}/exo_cluster.log" "Exo Cluster Log" ;;
            4) _logs_analysis ;;
            5) _logs_clean ;;
            6) _logs_list ;;
            b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

_logs_view() {
    local log_path="$1"
    local title="$2"
    cls
    section_header "$title"
    echo -e "  ${DIM}File: ${log_path}${NC}\n"

    if [[ -f "$log_path" ]]; then
        local lines
        lines="$(wc -l < "$log_path" 2>/dev/null || echo 0)"
        local size
        size="$(du -h "$log_path" 2>/dev/null | cut -f1)"
        echo -e "  ${DIM}Size: ${size} | Lines: ${lines}${NC}"
        echo -e "  ${DIM}$(printf '─%.0s' $(seq 1 50))${NC}\n"

        # Show last 40 lines
        tail -40 "$log_path" | while IFS= read -r line; do
            # Color-code by level
            if echo "$line" | grep -q '\[ERROR\]'; then
                echo -e "  ${RED}${line}${NC}"
            elif echo "$line" | grep -q '\[WARN\]'; then
                echo -e "  ${YELLOW}${line}${NC}"
            elif echo "$line" | grep -q '\[ACTION\]'; then
                echo -e "  ${CYAN}${line}${NC}"
            else
                echo -e "  ${DIM}${line}${NC}"
            fi
        done
    else
        echo -e "  ${ICON_OFF} Log file does not exist"
    fi

    press_any_key
}

_logs_analysis() {
    cls
    section_header "Log Analysis"
    log_action "Running log analysis"

    local log_files=("${LOG_FILE}" "${LOG_DIR}/mlx_lm_server.log" "${LOG_DIR}/exo_cluster.log")

    for lf in "${log_files[@]}"; do
        local name
        name="$(basename "$lf")"
        echo -e "  ${BOLD}${name}:${NC}"

        if [[ -f "$lf" ]]; then
            local total errors warnings actions info_count
            total="$(wc -l < "$lf" 2>/dev/null | tr -d ' ')"
            errors="$(grep -c '\[ERROR\]' "$lf" 2>/dev/null || echo 0)"
            warnings="$(grep -c '\[WARN\]' "$lf" 2>/dev/null || echo 0)"
            actions="$(grep -c '\[ACTION\]' "$lf" 2>/dev/null || echo 0)"
            info_count="$(grep -c '\[INFO\]' "$lf" 2>/dev/null || echo 0)"
            local size
            size="$(du -h "$lf" 2>/dev/null | cut -f1)"

            echo -e "    Size:     ${size}"
            echo -e "    Lines:    ${total}"
            echo -e "    ${RED}Errors:   ${errors}${NC}"
            echo -e "    ${YELLOW}Warnings: ${warnings}${NC}"
            echo -e "    ${CYAN}Actions:  ${actions}${NC}"
            echo -e "    Info:     ${info_count}"

            # Last error if any
            if (( errors > 0 )); then
                local last_err
                last_err="$(grep '\[ERROR\]' "$lf" | tail -1)"
                echo -e "    ${RED}Last error: ${last_err}${NC}"
            fi
        else
            echo -e "    ${DIM}(not found)${NC}"
        fi
        echo ""
    done

    press_any_key
}

_logs_clean() {
    cls
    section_header "Clean Old Logs"
    log_action "Cleaning old logs"

    echo -e "  ${DIM}Looking for rotated log files...${NC}\n"

    local cleaned=0
    while IFS= read -r rotated; do
        local size
        size="$(du -h "$rotated" 2>/dev/null | cut -f1)"
        echo -e "  ${ICON_ARROW} Removing: $(basename "$rotated") (${size})"
        rm -f "$rotated"
        cleaned=$((cleaned + 1))
    done < <(find "${LOG_DIR}" -name '*.log.[0-9]*' -type f 2>/dev/null)

    if (( cleaned == 0 )); then
        echo -e "  ${ICON_OK} No rotated logs to clean"
    else
        echo -e "\n  ${ICON_OK} Cleaned ${cleaned} rotated log file(s)"
        log_info "Cleaned ${cleaned} rotated log files"
    fi

    press_any_key
}

_logs_list() {
    cls
    section_header "All Log Files"
    echo -e "  ${DIM}Directory: ${LOG_DIR}${NC}\n"

    if [[ -d "${LOG_DIR}" ]]; then
        local count=0
        while IFS= read -r lf; do
            local name size modified
            name="$(basename "$lf")"
            size="$(du -h "$lf" 2>/dev/null | cut -f1)"
            modified="$(stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$lf" 2>/dev/null || stat --format='%y' "$lf" 2>/dev/null | cut -d. -f1 || echo '?')"
            echo -e "  ${ICON_ARROW} ${BOLD}${name}${NC}  ${DIM}(${size}, ${modified})${NC}"
            count=$((count + 1))
        done < <(find "${LOG_DIR}" -name '*.log*' -type f 2>/dev/null | sort)

        if (( count == 0 )); then
            echo -e "  ${DIM}No log files found${NC}"
        else
            echo -e "\n  ${DIM}Total: ${count} file(s)${NC}"
        fi
    else
        echo -e "  ${ICON_OFF} Log directory does not exist"
    fi

    press_any_key
}

# =============================================================================
# 7. HEALTH CHECK
# =============================================================================

health_check() {
    cls
    log_action "Running comprehensive health check"
    echo -e "\n  ${MAGENTA}${BOLD}Comprehensive Health Check${NC}"
    echo -e "  ${DIM}$(printf '═%.0s' $(seq 1 50))${NC}\n"

    local pass=0 fail=0 warn_count=0

    # -- System --
    echo -e "  ${BOLD}System${NC}"
    echo -e "  $(printf '─%.0s' $(seq 1 45))"

    # macOS check
    if [[ "$(uname -s)" == "Darwin" ]]; then
        echo -e "  ${ICON_OK} macOS detected ($(sw_vers -productVersion 2>/dev/null || echo '?'))"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_WARN} Not macOS — Apple Intelligence features limited"
        warn_count=$((warn_count + 1))
    fi

    # Apple Silicon
    if [[ "$(uname -m)" == "arm64" ]]; then
        echo -e "  ${ICON_OK} Apple Silicon ($(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'arm64'))"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_WARN} Not Apple Silicon — MLX/CoreML unavailable"
        warn_count=$((warn_count + 1))
    fi

    # Python
    if _cmd_exists python3; then
        local pyver
        pyver="$(python3 --version 2>/dev/null)"
        echo -e "  ${ICON_OK} ${pyver}"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_ERR} python3 not found"
        fail=$((fail + 1))
    fi
    echo ""

    # -- Python Packages --
    echo -e "  ${BOLD}Python Packages${NC}"
    echo -e "  $(printf '─%.0s' $(seq 1 45))"

    local packages=("mlx" "mlx_lm" "coremltools" "transformers" "huggingface_hub" "httpx")
    for pkg in "${packages[@]}"; do
        if python3 -c "import ${pkg}" 2>/dev/null; then
            local ver
            ver="$(python3 -c "import ${pkg}; print(getattr(${pkg}, '__version__', 'ok'))" 2>/dev/null || echo 'ok')"
            echo -e "  ${ICON_OK} ${pkg} (${ver})"
            pass=$((pass + 1))
        else
            echo -e "  ${ICON_OFF} ${pkg} — not installed"
            warn_count=$((warn_count + 1))
        fi
    done
    echo ""

    # -- Services --
    echo -e "  ${BOLD}Services${NC}"
    echo -e "  $(printf '─%.0s' $(seq 1 45))"

    # Mascarade Core
    if _http_ok "${MASCARADE_CORE_URL}/v1/health" 2; then
        echo -e "  ${ICON_OK} Mascarade Core API (${MASCARADE_CORE_URL})"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_ERR} Mascarade Core API — not reachable"
        fail=$((fail + 1))
    fi

    # Ollama
    if _http_ok "${OLLAMA_URL}/api/tags" 2; then
        echo -e "  ${ICON_OK} Ollama server (${OLLAMA_URL})"
        pass=$((pass + 1))
    else
        if _cmd_exists ollama; then
            echo -e "  ${ICON_WARN} Ollama installed but server not running"
            warn_count=$((warn_count + 1))
        else
            echo -e "  ${ICON_OFF} Ollama — not installed"
            warn_count=$((warn_count + 1))
        fi
    fi

    # MLX-LM server
    if _http_ok "${MLX_LM_URL}/health" 2 || _port_listening 8201; then
        echo -e "  ${ICON_OK} MLX-LM server (${MLX_LM_URL})"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_OFF} MLX-LM server — not running"
        warn_count=$((warn_count + 1))
    fi

    # Exo
    if _http_ok "${EXO_URL}/health" 2; then
        echo -e "  ${ICON_OK} Exo cluster (${EXO_URL})"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_OFF} Exo cluster — not active"
        warn_count=$((warn_count + 1))
    fi

    # Docker
    if _cmd_exists docker && docker info >/dev/null 2>&1; then
        echo -e "  ${ICON_OK} Docker daemon running"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_WARN} Docker — not running or not installed"
        warn_count=$((warn_count + 1))
    fi
    echo ""

    # -- P2P Mesh --
    echo -e "  ${BOLD}P2P Mesh${NC}"
    echo -e "  $(printf '─%.0s' $(seq 1 45))"
    local p2p
    p2p="$(_p2p_status)"
    if [[ -n "$p2p" ]]; then
        local peers node_id
        peers="$(echo "$p2p" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("peers",[])))' 2>/dev/null || echo '?')"
        node_id="$(echo "$p2p" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("node_id","?")[:16])' 2>/dev/null || echo '?')"
        echo -e "  ${ICON_OK} P2P active — ${peers} peers, node: ${node_id}..."
        pass=$((pass + 1))

        # List peers
        echo "$p2p" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for p in d.get('peers', []):
    name = p.get('name', p.get('node_id','?')[:12])
    addr = p.get('address', '?')
    print(f'       peer: {name} ({addr})')
" 2>/dev/null || true
    else
        echo -e "  ${ICON_OFF} P2P mesh — not available"
        warn_count=$((warn_count + 1))
    fi
    echo ""

    # -- Models --
    echo -e "  ${BOLD}Models${NC}"
    echo -e "  $(printf '─%.0s' $(seq 1 45))"
    if [[ -d "${MODELS_ROOT}" ]]; then
        local model_count
        model_count="$(find "${MODELS_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
        echo -e "  ${ICON_OK} Models directory exists (${model_count} model(s))"
        pass=$((pass + 1))
    else
        echo -e "  ${ICON_OFF} Models directory not found (${MODELS_ROOT})"
        warn_count=$((warn_count + 1))
    fi
    echo ""

    # -- Summary --
    echo -e "  ${DIM}$(printf '═%.0s' $(seq 1 50))${NC}"
    local total=$((pass + fail + warn_count))
    echo -e "  ${BOLD}Summary:${NC} ${GREEN}${pass} passed${NC} / ${YELLOW}${warn_count} warnings${NC} / ${RED}${fail} failed${NC} (${total} checks)"

    if (( fail > 0 )); then
        echo -e "  ${RED}${BOLD}Some checks failed — review above for details${NC}"
    elif (( warn_count > 0 )); then
        echo -e "  ${YELLOW}All critical checks passed, some optional components missing${NC}"
    else
        echo -e "  ${GREEN}${BOLD}All checks passed${NC}"
    fi

    log_info "Health check: ${pass} passed, ${warn_count} warnings, ${fail} failed"
    press_any_key
}

# =============================================================================
# MAIN MENU
# =============================================================================

main_menu() {
    while true; do
        cls
        banner

        echo -e "  ${BOLD}Main Menu${NC}\n"

        menu_item "1" "Status Dashboard" "Overview of all Apple Intelligence components"
        menu_item "2" "MLX-LM Management" "Install, start/stop, models, benchmarks"
        menu_item "3" "Exo Cluster" "Distributed inference across Apple devices"
        menu_item "4" "Model Registry" "List, convert, quantize, deploy models"
        menu_item "5" "Benchmark Suite" "Inference benchmarks & provider comparison"
        menu_item "6" "Logs" "View, analyze, clean log files"
        menu_item "7" "Health Check" "Comprehensive service & dependency check"
        echo ""
        menu_item "q" "Quit" "Exit the TUI"

        local choice
        choice="$(prompt_choice "Select")"

        case "$choice" in
            1) status_dashboard ;;
            2) mlx_lm_menu ;;
            3) exo_menu ;;
            4) model_registry_menu ;;
            5) benchmark_menu ;;
            6) logs_menu ;;
            7) health_check ;;
            q|Q)
                cls
                echo -e "\n  ${DIM}Au revoir! KEEP THE BEAT${NC}\n"
                log_action "TUI session ended"
                exit 0
                ;;
            *)
                # Invalid input, just redraw
                ;;
        esac
    done
}

# =============================================================================
# ENTRY POINT
# =============================================================================

# Parse arguments
case "${1:-}" in
    -h|--help)
        cat <<'EOF'
Usage: scripts/apple_intelligence_tui.sh [options]

Interactive TUI for managing Apple Intelligence integration in Mascarade.

Sections:
  1. Status Dashboard    — Component status overview
  2. MLX-LM Management   — Install, run, benchmark MLX-LM
  3. Exo Cluster         — Distributed inference management
  4. Model Registry      — Convert, quantize, deploy models
  5. Benchmark Suite     — Performance testing & comparison
  6. Logs                — Log viewing, analysis, cleanup
  7. Health Check        — Comprehensive dependency check

Options:
  --status     Show status dashboard and exit
  --health     Run health check and exit
  -h, --help   Show this help

Environment:
  MASCARADE_CORE_URL   Mascarade API URL (default: http://localhost:8100)
  OLLAMA_URL           Ollama server URL (default: http://localhost:11434)
  MLX_LM_URL           MLX-LM server URL (default: http://localhost:8201)
  EXO_URL              Exo cluster URL (default: http://localhost:52415)
  APPLE_MODELS_ROOT    Local models directory (default: ~/Models/mascarade/apple-llm)

Logs:
  All actions are logged to logs/apple_intelligence_tui.log
  Automatic rotation at 10MB, keeps last 5 rotated files.
EOF
        exit 0
        ;;
    --status)
        # Non-interactive: show dashboard and exit
        log_action "TUI session started (--status mode)"
        status_dashboard
        exit 0
        ;;
    --health)
        # Non-interactive: run health check and exit
        log_action "TUI session started (--health mode)"
        health_check
        exit 0
        ;;
esac

# Trap for clean exit
trap 'echo -e "\n  ${DIM}Interrupted. Au revoir!${NC}"; log_action "TUI session interrupted"; exit 0' INT TERM

# Log session start
log_action "TUI session started"

# Launch main menu
main_menu
