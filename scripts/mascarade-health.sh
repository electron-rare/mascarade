#!/usr/bin/env bash
# scripts/mascarade-health.sh — One-shot health check for Mascarade services
# Checks core, api, and docker containers. Exits 0 if all healthy, 1 otherwise.
# Suitable for cron jobs, CI pipelines, and scripted monitoring.

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
CORE_URL="${MASCARADE_CORE_URL:-http://localhost:8100}"
API_URL="${MASCARADE_API_URL:-http://localhost:3000}"
API_KEY="${MASCARADE_API_KEY:-}"
CURL_TIMEOUT=5
VERBOSE="${VERBOSE:-false}"
EXIT_CODE=0

# ── Colors (respect NO_COLOR) ─────────────────────────────────────────────────
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m'
    DIM='\033[2m'
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
    MAGENTA='\033[0;35m'
    NC='\033[0m'
else
    BOLD='' DIM='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' NC=''
fi

# ── Helpers ────────────────────────────────────────────────────────────────────
ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }
err()  { echo -e "  ${RED}✗${NC} $*"; }
info() { echo -e "  ${DIM}$*${NC}"; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}$*${NC}"; echo -e "  ${DIM}──────────────────────────────────────────${NC}"; }

usage() {
    cat <<'EOF'
Usage: mascarade-health.sh [options]

One-shot health check for all Mascarade services.

Options:
  --core-url URL     Core service URL (default: http://localhost:8100)
  --api-url  URL     API service URL  (default: http://localhost:3000)
  --api-key  KEY     API auth key (or set MASCARADE_API_KEY)
  --verbose          Show extra details
  --quiet            Only output on failure
  -h, --help         Show this help

Exit codes:
  0  All services healthy
  1  One or more services degraded or unreachable
EOF
}

QUIET=false

# ── Argument parsing ───────────────────────────────────────────────────────────
while (( $# > 0 )); do
    case "$1" in
        --core-url) CORE_URL="${2:?missing value}"; shift 2 ;;
        --api-url)  API_URL="${2:?missing value}";  shift 2 ;;
        --api-key)  API_KEY="${2:?missing value}";  shift 2 ;;
        --verbose)  VERBOSE=true; shift ;;
        --quiet)    QUIET=true; shift ;;
        -h|--help)  usage; exit 0 ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

# ── HTTP check helper ─────────────────────────────────────────────────────────
# check_endpoint LABEL URL
# Returns: sets EXIT_CODE=1 on failure
check_endpoint() {
    local label="$1" url="$2"
    local http_code body
    local -a curl_args=(--silent --max-time "$CURL_TIMEOUT" --write-out '%{http_code}')

    if [[ -n "$API_KEY" ]]; then
        curl_args+=(-H "Authorization: Bearer $API_KEY")
    fi

    local tmpfile
    tmpfile="$(mktemp /tmp/mascarade-health.XXXXXX)"

    http_code="$(curl "${curl_args[@]}" -o "$tmpfile" "$url" 2>/dev/null || echo "000")"
    body="$(cat "$tmpfile" 2>/dev/null || true)"
    rm -f "$tmpfile"

    if [[ "$http_code" == "200" ]]; then
        if [[ "$QUIET" != true ]]; then
            ok "$label: healthy (HTTP $http_code)"
            if [[ "$VERBOSE" == true ]] && command -v jq &>/dev/null && [[ -n "$body" ]]; then
                local version
                version="$(echo "$body" | jq -r '.version // empty' 2>/dev/null || true)"
                [[ -n "$version" ]] && info "  version: $version"
            fi
        fi
    elif [[ "$http_code" == "000" ]]; then
        if [[ "$QUIET" != true ]]; then
            err "$label: unreachable (connection refused or timeout)"
        fi
        EXIT_CODE=1
    else
        if [[ "$QUIET" != true ]]; then
            warn "$label: degraded (HTTP $http_code)"
        fi
        EXIT_CODE=1
    fi
}

# ── Docker check ──────────────────────────────────────────────────────────────
check_docker() {
    if ! command -v docker &>/dev/null; then
        [[ "$QUIET" != true ]] && info "docker not available, skipping container checks"
        return
    fi

    if ! docker info &>/dev/null 2>&1; then
        [[ "$QUIET" != true ]] && warn "docker daemon not reachable"
        return
    fi

    local containers
    containers="$(docker ps --filter 'name=mascarade' --format '{{.Names}}\t{{.Status}}' 2>/dev/null || true)"

    if [[ -z "$containers" ]]; then
        [[ "$QUIET" != true ]] && info "no mascarade docker containers found"
        return
    fi

    while IFS=$'\t' read -r name status; do
        if [[ "$status" == *"Up"* ]]; then
            [[ "$QUIET" != true ]] && ok "container $name: $status"
        else
            [[ "$QUIET" != true ]] && err "container $name: $status"
            EXIT_CODE=1
        fi
    done <<< "$containers"

    # Check for containers with health status
    local unhealthy
    unhealthy="$(docker ps --filter 'name=mascarade' --filter 'health=unhealthy' --format '{{.Names}}' 2>/dev/null || true)"
    if [[ -n "$unhealthy" ]]; then
        while IFS= read -r name; do
            [[ "$QUIET" != true ]] && err "container $name: unhealthy"
            EXIT_CODE=1
        done <<< "$unhealthy"
    fi
}

# ── Main ───────────────────────────────────────────────────────────────────────
main() {
    if [[ "$QUIET" != true ]]; then
        echo ""
        echo -e "  ${BOLD}${CYAN}mascarade health check${NC}  $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
    fi

    section "Services"
    check_endpoint "Core  ($CORE_URL/health)" "$CORE_URL/health"
    check_endpoint "API   ($API_URL/health)"  "$API_URL/health"

    section "Providers"
    check_endpoint "Providers status" "$API_URL/api/providers/status"

    section "Scheduler"
    check_endpoint "Scheduler" "$API_URL/api/scheduler/status"

    section "Docker"
    check_docker

    echo ""
    if [[ "$EXIT_CODE" -eq 0 ]]; then
        ok "${BOLD}All checks passed${NC}"
    else
        err "${BOLD}Some checks failed${NC}"
    fi
    echo ""

    exit "$EXIT_CODE"
}

main
