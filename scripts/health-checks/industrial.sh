#!/usr/bin/env bash
# scripts/health-checks/industrial.sh - Health check for industrial profile services
set -euo pipefail

# ── Configuration ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Industrial profile services
INDUSTRIAL_SERVICES=("agent-factory-cockpit" "agent-factory-dcs-sandbox" "edge-proxy" "ops-agent")

# ── Colors ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' NC=''
fi

# ── Logging ──
ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
err()  { echo -e "  ${RED}✗${NC} $*" >&2; }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }
info() { echo -e "  ${CYAN}▸${NC} $*"; }

# ── Health check function ──
check_service_health() {
    local service="$1"
    local status
    local health

    # Get service status using docker compose ps with JSON format
    local ps_output
    ps_output=$(cd "$REPO_DIR" && docker compose ps --format json "$service" 2>/dev/null || echo "[]")

    if [[ "$ps_output" == "[]" || -z "$ps_output" ]]; then
        err "$service: not running"
        return 1
    fi

    # Parse JSON to get State and Health
    # docker compose ps returns one JSON object per line
    status=$(echo "$ps_output" | grep -o '"State":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "unknown")
    health=$(echo "$ps_output" | grep -o '"Health":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")

    # Check if service is running
    if [[ "$status" != "running" ]]; then
        err "$service: $status (expected: running)"
        return 1
    fi

    # Check health status if available
    if [[ -n "$health" ]]; then
        if [[ "$health" == "healthy" ]]; then
            ok "$service: running and healthy"
            return 0
        else
            warn "$service: running but $health"
            return 1
        fi
    else
        # No health check defined, just verify it's running
        ok "$service: running"
        return 0
    fi
}

# ── Main ──
main() {
    info "Checking industrial profile services..."
    echo ""

    local failed=0

    for service in "${INDUSTRIAL_SERVICES[@]}"; do
        if ! check_service_health "$service"; then
            ((failed++)) || true
        fi
    done

    echo ""

    if [[ $failed -eq 0 ]]; then
        ok "All industrial services healthy (${#INDUSTRIAL_SERVICES[@]}/${#INDUSTRIAL_SERVICES[@]})"
        return 0
    else
        err "$failed/${#INDUSTRIAL_SERVICES[@]} industrial services failed health check"
        return 1
    fi
}

# ── Run ──
main "$@"
