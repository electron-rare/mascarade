#!/usr/bin/env bash
# Test script for core profile E2E verification
# Subtask 3-4: Test core profile starts correctly with minimal resources

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
err() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# Cleanup function
cleanup() {
    info "Cleaning up - stopping core profile services..."
    docker compose --profile core down 2>/dev/null || true
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

info "=== Core Profile E2E Test ==="
echo ""

# Step 1: Verify docker-compose.yml has profiles
info "Step 1: Verifying docker-compose.yml has core profile tags..."
if ! grep -q "profiles:" "$REPO_DIR/docker-compose.yml"; then
    err "docker-compose.yml does not contain profile tags"
    exit 1
fi

# Verify core services have core profile
for svc in core api redis postgres; do
    if ! grep -A3 "^  $svc:" "$REPO_DIR/docker-compose.yml" | grep -- "- core" >/dev/null 2>&1; then
        err "Service $svc does not have core profile"
        exit 1
    fi
    info "  ✓ $svc has core profile"
done

echo ""

# Step 2: Start core profile services
info "Step 2: Starting core profile services..."
if ! docker compose --profile core up -d; then
    err "Failed to start core profile services"
    exit 1
fi

echo ""

# Step 3: Wait for services to start
info "Step 3: Waiting 30 seconds for services to start..."
sleep 30

echo ""

# Step 4: Run health checks
info "Step 4: Running core profile health checks..."
if ! bash "$REPO_DIR/scripts/health-checks/core.sh"; then
    err "Core profile health checks failed"
    exit 1
fi

echo ""

# Step 5: Verify container count
info "Step 5: Verifying only core services are running..."
running_count=$(docker compose ps --format json | jq -r 'select(.State == "running") | .Service' | wc -l | tr -d ' ')

if [[ "$running_count" != "4" ]]; then
    err "Expected 4 containers running, found $running_count"
    docker compose ps
    exit 1
fi

info "  ✓ Exactly 4 containers running (core, api, redis, postgres)"

# Verify it's the right services
expected_services=("core" "api" "redis" "postgres")
for svc in "${expected_services[@]}"; do
    if ! docker compose ps --format json | jq -r '.Service' | grep "^$svc$" >/dev/null 2>&1; then
        err "Expected service $svc not found"
        exit 1
    fi
    info "  ✓ $svc is running"
done

echo ""

# Step 6: Verify no other profiles started
info "Step 6: Verifying no services from other profiles are running..."
other_services=$(docker compose ps --format json | jq -r '.Service' | grep -v -E "^(core|api|redis|postgres)$" || true)
if [[ -n "$other_services" ]]; then
    warn "Unexpected services running:"
    echo "$other_services"
    exit 1
fi
info "  ✓ No services from other profiles are running"

echo ""
echo -e "${GREEN}=== Core Profile E2E Test PASSED ===${NC}"
echo ""

exit 0
