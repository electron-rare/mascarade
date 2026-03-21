#!/usr/bin/env bash
# scripts/mascarade-monitor.sh — Real-time TUI monitor for Mascarade operations
# Displays service health, providers, agents, P2P mesh, traces, scheduler, docker.
# Auto-refreshes every 10s. Keyboard: q=quit, r=refresh, p=providers, t=traces.
#
# shellcheck disable=SC2034

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
CORE_URL="${MASCARADE_CORE_URL:-http://localhost:8100}"
API_URL="${MASCARADE_API_URL:-http://localhost:3000}"
API_KEY="${MASCARADE_API_KEY:-}"
REFRESH_SECONDS="${MASCARADE_MONITOR_INTERVAL:-10}"
LOG_FILE="/tmp/mascarade-monitor.log"
CURL_TIMEOUT=3

# ── Color helpers (tput with fallback) ─────────────────────────────────────────
setup_colors() {
    if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]] && command -v tput &>/dev/null; then
        BOLD="$(tput bold 2>/dev/null || true)"
        DIM="$(tput dim 2>/dev/null || true)"
        REV="$(tput rev 2>/dev/null || true)"
        RESET="$(tput sgr0 2>/dev/null || true)"
        RED="$(tput setaf 1 2>/dev/null || true)"
        GREEN="$(tput setaf 2 2>/dev/null || true)"
        YELLOW="$(tput setaf 3 2>/dev/null || true)"
        BLUE="$(tput setaf 4 2>/dev/null || true)"
        MAGENTA="$(tput setaf 5 2>/dev/null || true)"
        CYAN="$(tput setaf 6 2>/dev/null || true)"
        WHITE="$(tput setaf 7 2>/dev/null || true)"
        COLS="$(tput cols 2>/dev/null || echo 80)"
        ROWS="$(tput lines 2>/dev/null || echo 24)"
    else
        BOLD="" DIM="" REV="" RESET="" RED="" GREEN="" YELLOW=""
        BLUE="" MAGENTA="" CYAN="" WHITE=""
        COLS=80 ROWS=24
    fi
}

# ── Logging ────────────────────────────────────────────────────────────────────
log_action() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] $*" >> "$LOG_FILE"
}

# ── Terminal management ────────────────────────────────────────────────────────
cleanup() {
    # Restore terminal state
    tput cnorm 2>/dev/null || true   # show cursor
    tput rmcup 2>/dev/null || true   # restore screen
    stty echo 2>/dev/null || true
    log_action "Monitor stopped"
    echo "mascarade-monitor exited."
}

init_terminal() {
    tput smcup 2>/dev/null || true   # alternate screen
    tput civis 2>/dev/null || true   # hide cursor
    stty -echo 2>/dev/null || true
    trap cleanup EXIT INT TERM HUP
    log_action "Monitor started (core=$CORE_URL api=$API_URL)"
}

move_to() {
    tput cup "$1" "$2" 2>/dev/null || true
}

clear_screen() {
    tput clear 2>/dev/null || printf '\033[2J\033[H'
}

# ── HTTP helpers ───────────────────────────────────────────────────────────────
_auth_header() {
    if [[ -n "$API_KEY" ]]; then
        echo "-H" "Authorization: Bearer $API_KEY"
    fi
}

# Fetch a URL, return body on stdout. Sets _HTTP_CODE as side-effect.
fetch() {
    local url="$1"
    local tmpfile
    tmpfile="$(mktemp /tmp/mascarade-monitor-fetch.XXXXXX)"

    local -a curl_args=(--silent --max-time "$CURL_TIMEOUT" --write-out '%{http_code}' -o "$tmpfile")
    if [[ -n "$API_KEY" ]]; then
        curl_args+=(-H "Authorization: Bearer $API_KEY")
    fi

    _HTTP_CODE="$(curl "${curl_args[@]}" "$url" 2>/dev/null || echo "000")"
    if [[ -f "$tmpfile" ]]; then
        cat "$tmpfile"
        rm -f "$tmpfile"
    fi
}

# Convenience: fetch JSON and extract a field with lightweight parsing.
# Usage: json_field '{"key":"val"}' key
# Falls back gracefully if jq is unavailable.
json_field() {
    local json="$1" field="$2"
    if command -v jq &>/dev/null; then
        echo "$json" | jq -r ".$field // empty" 2>/dev/null || true
    else
        # Naive extraction for simple cases
        echo "$json" | sed -n "s/.*\"$field\"[[:space:]]*:[[:space:]]*\"\{0,1\}\([^,\"}\]*\)\"\{0,1\}.*/\1/p" | head -1
    fi
}

json_array_length() {
    local json="$1" field="$2"
    if command -v jq &>/dev/null; then
        echo "$json" | jq ".$field | if type == \"array\" then length else 0 end" 2>/dev/null || echo 0
    else
        echo "?"
    fi
}

# ── Status formatting ─────────────────────────────────────────────────────────
status_icon() {
    case "$1" in
        ok|healthy|running|up|active)    printf '%s●%s' "$GREEN" "$RESET" ;;
        warn|degraded|partial|starting)  printf '%s●%s' "$YELLOW" "$RESET" ;;
        error|down|unhealthy|stopped)    printf '%s●%s' "$RED" "$RESET" ;;
        *)                               printf '%s●%s' "$DIM" "$RESET" ;;
    esac
}

status_text() {
    case "$1" in
        ok|healthy|running|up|active)    printf '%s%s%s' "$GREEN" "$1" "$RESET" ;;
        warn|degraded|partial|starting)  printf '%s%s%s' "$YELLOW" "$1" "$RESET" ;;
        error|down|unhealthy|stopped)    printf '%s%s%s' "$RED" "$1" "$RESET" ;;
        *)                               printf '%s%s%s' "$DIM" "${1:-unknown}" "$RESET" ;;
    esac
}

# Print a padded line to fill terminal width (avoids leftover chars on redraw).
padline() {
    local text="$1"
    printf '%-*s\n' "$COLS" "$text"
}

# ── Data fetchers ──────────────────────────────────────────────────────────────
CORE_HEALTH="" CORE_STATUS="unknown"
API_HEALTH=""  API_STATUS="unknown"
PROVIDERS_DATA="" AGENTS_DATA="" P2P_DATA="" TRACES_DATA="" SCHEDULER_DATA=""

fetch_all() {
    # Core health
    CORE_HEALTH="$(fetch "$CORE_URL/health")"
    if [[ "$_HTTP_CODE" == "200" ]]; then
        CORE_STATUS="ok"
    elif [[ "$_HTTP_CODE" == "000" ]]; then
        CORE_STATUS="down"
    else
        CORE_STATUS="error"
    fi

    # API health
    API_HEALTH="$(fetch "$API_URL/health")"
    if [[ "$_HTTP_CODE" == "200" ]]; then
        API_STATUS="ok"
    elif [[ "$_HTTP_CODE" == "000" ]]; then
        API_STATUS="down"
    else
        API_STATUS="error"
    fi

    # Provider status
    PROVIDERS_DATA="$(fetch "$API_URL/api/providers/status")"

    # Agents
    AGENTS_DATA="$(fetch "$API_URL/api/agents")"

    # P2P mesh
    P2P_DATA="$(fetch "$CORE_URL/cluster/p2p/status")"

    # Recent traces
    TRACES_DATA="$(fetch "$API_URL/agent-traces/recent?limit=5")"

    # Scheduler
    SCHEDULER_DATA="$(fetch "$API_URL/api/scheduler/status")"

    log_action "Data refresh (core=$CORE_STATUS api=$API_STATUS)"
}

# ── Docker status ──────────────────────────────────────────────────────────────
DOCKER_AVAILABLE=false
DOCKER_CONTAINERS=""

fetch_docker() {
    if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
        DOCKER_AVAILABLE=true
        DOCKER_CONTAINERS="$(docker ps --filter 'name=mascarade' --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || true)"
    else
        DOCKER_AVAILABLE=false
        DOCKER_CONTAINERS=""
    fi
}

# ── Render sections ───────────────────────────────────────────────────────────
render_header() {
    local ts
    ts="$(date '+%H:%M:%S')"
    printf '%s' "$BOLD$CYAN"
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │  ░▒▓ mascarade ▓▒░  real-time monitor       │"
    echo "  └─────────────────────────────────────────────┘"
    printf '%s' "$RESET"
    printf '  %score=%s  api=%s%s   %s[%s]%s  refresh=%ss\n' \
        "$DIM" "$CORE_URL" "$API_URL" "$RESET" \
        "$DIM" "$ts" "$RESET" "$REFRESH_SECONDS"
    echo ""
}

render_services() {
    printf '  %s%s SERVICE HEALTH %s\n' "$BOLD" "$MAGENTA" "$RESET"
    printf '  %-20s %s\n' "Core ($CORE_URL)" "$(status_icon "$CORE_STATUS") $(status_text "$CORE_STATUS")"

    local core_version
    core_version="$(json_field "$CORE_HEALTH" "version")"
    if [[ -n "$core_version" ]]; then
        printf '  %-20s %s%s%s\n' "" "${DIM}version: $core_version${RESET}" "" ""
    fi

    printf '  %-20s %s\n' "API  ($API_URL)" "$(status_icon "$API_STATUS") $(status_text "$API_STATUS")"

    local api_version
    api_version="$(json_field "$API_HEALTH" "version")"
    if [[ -n "$api_version" ]]; then
        printf '  %-20s %s\n' "" "${DIM}version: $api_version${RESET}"
    fi
    echo ""
}

render_providers() {
    printf '  %s%s PROVIDERS %s\n' "$BOLD" "$MAGENTA" "$RESET"
    if [[ -z "$PROVIDERS_DATA" || "$PROVIDERS_DATA" == "null" ]]; then
        printf '  %s(no data)%s\n' "$DIM" "$RESET"
    elif command -v jq &>/dev/null; then
        # Try to iterate provider entries
        local count
        count="$(echo "$PROVIDERS_DATA" | jq 'if type == "array" then length elif type == "object" then (keys | length) else 0 end' 2>/dev/null || echo 0)"
        if [[ "$count" -gt 0 ]]; then
            echo "$PROVIDERS_DATA" | jq -r '
                if type == "array" then
                    .[] | "  \(.name // .id // "provider"): \(.status // "unknown") (\(.model // "-"))"
                elif type == "object" then
                    to_entries[] | "  \(.key): \(.value.status // .value // "unknown")"
                else
                    "  (unexpected format)"
                end
            ' 2>/dev/null | head -8 | while IFS= read -r line; do
                echo "$line"
            done
        else
            printf '  %s(empty)%s\n' "$DIM" "$RESET"
        fi
    else
        printf '  %s(install jq for details)%s\n' "$DIM" "$RESET"
    fi
    echo ""
}

render_agents() {
    printf '  %s%s AGENTS %s\n' "$BOLD" "$MAGENTA" "$RESET"
    if [[ -z "$AGENTS_DATA" || "$AGENTS_DATA" == "null" ]]; then
        printf '  %s(no data)%s\n' "$DIM" "$RESET"
    elif command -v jq &>/dev/null; then
        local count
        count="$(echo "$AGENTS_DATA" | jq 'if type == "array" then length else 0 end' 2>/dev/null || echo 0)"
        printf '  count: %s%s%s\n' "$BOLD" "$count" "$RESET"
        if [[ "$count" -gt 0 ]]; then
            echo "$AGENTS_DATA" | jq -r '
                if type == "array" then
                    .[:8][] | "  - \(.name // .id // "agent") [\(.status // "unknown")]"
                else empty end
            ' 2>/dev/null | while IFS= read -r line; do
                echo "$line"
            done
        fi
    else
        printf '  %s(install jq for details)%s\n' "$DIM" "$RESET"
    fi
    echo ""
}

render_p2p() {
    printf '  %s%s P2P MESH %s\n' "$BOLD" "$MAGENTA" "$RESET"
    if [[ -z "$P2P_DATA" || "$P2P_DATA" == "null" ]]; then
        printf '  %s(no data)%s\n' "$DIM" "$RESET"
    elif command -v jq &>/dev/null; then
        local peers connected
        peers="$(json_field "$P2P_DATA" "peers")"
        connected="$(json_field "$P2P_DATA" "connected")"
        local mesh_status
        mesh_status="$(json_field "$P2P_DATA" "status")"
        [[ -z "$mesh_status" ]] && mesh_status="unknown"

        printf '  status: %s' "$(status_text "$mesh_status")"
        [[ -n "$peers" ]] && printf '  peers: %s' "$peers"
        [[ -n "$connected" ]] && printf '  connected: %s' "$connected"
        echo ""

        # Show peer list if available
        echo "$P2P_DATA" | jq -r '
            .peer_list // .nodes // empty |
            if type == "array" then .[:6][] | "  - \(.id // .name // .addr // .)" else empty end
        ' 2>/dev/null || true
    else
        printf '  %s(install jq for details)%s\n' "$DIM" "$RESET"
    fi
    echo ""
}

render_traces() {
    printf '  %s%s RECENT TRACES (last 5) %s\n' "$BOLD" "$MAGENTA" "$RESET"
    if [[ -z "$TRACES_DATA" || "$TRACES_DATA" == "null" ]]; then
        printf '  %s(no data)%s\n' "$DIM" "$RESET"
    elif command -v jq &>/dev/null; then
        echo "$TRACES_DATA" | jq -r '
            (if type == "object" then .traces // .data // [] elif type == "array" then . else [] end)
            | .[:5][] |
            "  \(.timestamp // .created_at // "-" | split("T") | .[1] // .[0] | split(".")[0]) \(.agent_name // .agent // "-") \(.status // .state // "-") \(.duration_ms // "-")ms"
        ' 2>/dev/null | while IFS= read -r line; do
            echo "$line"
        done
        local shown
        shown="$(echo "$TRACES_DATA" | jq '(if type == "object" then .traces // .data // [] elif type == "array" then . else [] end) | length' 2>/dev/null || echo 0)"
        [[ "$shown" == "0" ]] && printf '  %s(empty)%s\n' "$DIM" "$RESET"
    else
        printf '  %s(install jq for details)%s\n' "$DIM" "$RESET"
    fi
    echo ""
}

render_scheduler() {
    printf '  %s%s SCHEDULER %s\n' "$BOLD" "$MAGENTA" "$RESET"
    if [[ -z "$SCHEDULER_DATA" || "$SCHEDULER_DATA" == "null" ]]; then
        printf '  %s(no data)%s\n' "$DIM" "$RESET"
    elif command -v jq &>/dev/null; then
        local sched_status workers_active workers_total
        sched_status="$(json_field "$SCHEDULER_DATA" "status")"
        workers_active="$(json_field "$SCHEDULER_DATA" "workers_active")"
        workers_total="$(json_field "$SCHEDULER_DATA" "workers_total")"
        [[ -z "$sched_status" ]] && sched_status="unknown"
        printf '  status: %s' "$(status_text "$sched_status")"
        if [[ -n "$workers_active" && -n "$workers_total" ]]; then
            printf '  workers: %s/%s' "$workers_active" "$workers_total"
        fi
        echo ""

        # Show queued/running jobs if available
        echo "$SCHEDULER_DATA" | jq -r '
            .jobs // .queue // empty |
            if type == "array" then .[:5][] |
                "  \(.id // "-"): \(.state // .status // "?") (\(.type // .name // "-"))"
            else empty end
        ' 2>/dev/null || true
    else
        printf '  %s(install jq for details)%s\n' "$DIM" "$RESET"
    fi
    echo ""
}

render_docker() {
    printf '  %s%s DOCKER CONTAINERS %s\n' "$BOLD" "$MAGENTA" "$RESET"
    if [[ "$DOCKER_AVAILABLE" != true ]]; then
        printf '  %s(docker not available)%s\n' "$DIM" "$RESET"
    elif [[ -z "$DOCKER_CONTAINERS" ]]; then
        printf '  %s(no mascarade containers running)%s\n' "$DIM" "$RESET"
    else
        while IFS=$'\t' read -r name status ports; do
            local icon
            if [[ "$status" == *"Up"* ]]; then
                icon="$(status_icon "running")"
            else
                icon="$(status_icon "stopped")"
            fi
            printf '  %s %-28s %s' "$icon" "$name" "$status"
            [[ -n "$ports" ]] && printf '  %s%s%s' "$DIM" "$ports" "$RESET"
            echo ""
        done <<< "$DOCKER_CONTAINERS"
    fi
    echo ""
}

render_footer() {
    local footer
    footer="  ${DIM}[q]uit  [r]efresh  [p]roviders detail  [t]races detail${RESET}"
    # Position at bottom
    move_to "$((ROWS - 1))" 0
    printf '%s' "$footer"
}

# ── Detail views ───────────────────────────────────────────────────────────────
show_providers_detail() {
    clear_screen
    move_to 0 0
    printf '  %s%s PROVIDERS DETAIL %s\n\n' "$BOLD" "$CYAN" "$RESET"

    local data
    data="$(fetch "$API_URL/api/providers/status")"
    if command -v jq &>/dev/null && [[ -n "$data" ]]; then
        echo "$data" | jq '.' 2>/dev/null || echo "$data"
    else
        echo "$data"
    fi

    echo ""
    printf '  %sPress any key to return...%s' "$DIM" "$RESET"
    read -rsn1 -t 30 _ || true
    log_action "Viewed providers detail"
}

show_traces_detail() {
    clear_screen
    move_to 0 0
    printf '  %s%s TRACES DETAIL %s\n\n' "$BOLD" "$CYAN" "$RESET"

    local data
    data="$(fetch "$API_URL/agent-traces/recent?limit=20")"
    if command -v jq &>/dev/null && [[ -n "$data" ]]; then
        echo "$data" | jq '.' 2>/dev/null | head -60 || echo "$data" | head -60
    else
        echo "$data" | head -60
    fi

    echo ""
    printf '  %sPress any key to return...%s' "$DIM" "$RESET"
    read -rsn1 -t 30 _ || true
    log_action "Viewed traces detail"
}

# ── Main render ────────────────────────────────────────────────────────────────
render_dashboard() {
    clear_screen
    move_to 0 0
    render_header
    render_services
    render_providers
    render_agents
    render_p2p
    render_traces
    render_scheduler
    render_docker
    render_footer
}

# ── Usage ──────────────────────────────────────────────────────────────────────
usage() {
    cat <<'EOF'
Usage: mascarade-monitor.sh [options]

Real-time TUI monitor for Mascarade operations.

Options:
  --core-url URL     Core service URL (default: http://localhost:8100)
  --api-url  URL     API service URL  (default: http://localhost:3000)
  --api-key  KEY     API auth key (or set MASCARADE_API_KEY)
  --interval N       Refresh interval in seconds (default: 10)
  -h, --help         Show this help

Keyboard:
  q  Quit          r  Force refresh
  p  Providers     t  Traces detail

Environment:
  MASCARADE_CORE_URL, MASCARADE_API_URL, MASCARADE_API_KEY,
  MASCARADE_MONITOR_INTERVAL, NO_COLOR
EOF
}

# ── Argument parsing ───────────────────────────────────────────────────────────
parse_args() {
    while (( $# > 0 )); do
        case "$1" in
            --core-url) CORE_URL="${2:?missing value}"; shift 2 ;;
            --api-url)  API_URL="${2:?missing value}";  shift 2 ;;
            --api-key)  API_KEY="${2:?missing value}";  shift 2 ;;
            --interval) REFRESH_SECONDS="${2:?missing value}"; shift 2 ;;
            -h|--help)  usage; exit 0 ;;
            *)
                echo "Unknown option: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done
}

# ── Main loop ──────────────────────────────────────────────────────────────────
main() {
    parse_args "$@"
    setup_colors
    init_terminal

    while true; do
        # Refresh dimensions on each cycle (terminal may resize)
        COLS="$(tput cols 2>/dev/null || echo 80)"
        ROWS="$(tput lines 2>/dev/null || echo 24)"

        fetch_all
        fetch_docker
        render_dashboard

        # Wait for timeout or keypress
        local key=""
        if read -rsn1 -t "$REFRESH_SECONDS" key 2>/dev/null; then
            case "$key" in
                q|Q)
                    log_action "Quit by user"
                    break
                    ;;
                r|R)
                    log_action "Manual refresh"
                    continue
                    ;;
                p|P)
                    show_providers_detail
                    continue
                    ;;
                t|T)
                    show_traces_detail
                    continue
                    ;;
            esac
        fi
    done
}

main "$@"
