#!/usr/bin/env bash
# Test script for core + observability profile E2E verification
# Subtask 3-5: Test observability profile adds monitoring stack to core

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
    info "Cleaning up - stopping core and observability profile services..."
    docker compose --profile core --profile observability down 2>/dev/null || true
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

info "=== Core + Observability Profile E2E Test ==="
echo ""

# Step 1: Verify docker-compose.yml has profiles
info "Step 1: Verifying docker-compose.yml has core and observability profile tags..."
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

# Verify observability services have observability profile
for svc in grafana prometheus loki tempo promtail otel-collector blackbox-exporter; do
    if ! grep -A3 "^  $svc:" "$REPO_DIR/docker-compose.yml" | grep -- "- observability" >/dev/null 2>&1; then
        err "Service $svc does not have observability profile"
        exit 1
    fi
    info "  ✓ $svc has observability profile"
done

echo ""

# Step 2: Start core + observability profile services
info "Step 2: Starting core and observability profile services..."
if ! docker compose --profile core --profile observability up -d; then
    err "Failed to start core + observability profile services"
    exit 1
fi

echo ""

# Step 3: Wait for services to start
info "Step 3: Waiting 45 seconds for services to start..."
sleep 45

echo ""

# Step 4: Run core health checks
info "Step 4a: Running core profile health checks..."
if ! bash "$REPO_DIR/scripts/health-checks/core.sh"; then
    err "Core profile health checks failed"
    exit 1
fi

echo ""

# Step 4b: Run observability health checks
info "Step 4b: Running observability profile health checks..."
if ! bash "$REPO_DIR/scripts/health-checks/observability.sh"; then
    err "Observability profile health checks failed"
    exit 1
fi

echo ""

# Step 5: Verify container count
info "Step 5: Verifying ~11 containers are running (core + observability)..."
running_count=$(docker compose ps --format json | jq -r 'select(.State == "running") | .Service' | wc -l | tr -d ' ')

if [[ "$running_count" -lt 11 ]]; then
    err "Expected at least 11 containers running, found $running_count"
    docker compose ps
    exit 1
fi

info "  ✓ $running_count containers running (expected ~11)"

# Verify core services
core_services=("core" "api" "redis" "postgres")
for svc in "${core_services[@]}"; do
    if ! docker compose ps --format json | jq -r '.Service' | grep "^$svc$" >/dev/null 2>&1; then
        err "Expected core service $svc not found"
        exit 1
    fi
    info "  ✓ $svc is running (core)"
done

# Verify observability services
observability_services=("grafana" "prometheus" "loki" "tempo" "promtail" "otel-collector" "blackbox-exporter")
for svc in "${observability_services[@]}"; do
    if ! docker compose ps --format json | jq -r '.Service' | grep "^$svc$" >/dev/null 2>&1; then
        err "Expected observability service $svc not found"
        exit 1
    fi
    info "  ✓ $svc is running (observability)"
done

echo ""

# Step 6: Test Grafana API endpoint
info "Step 6: Testing Grafana API endpoint..."
max_retries=5
retry_count=0
while [[ $retry_count -lt $max_retries ]]; do
    if curl -fsS http://localhost:3001/api/health >/dev/null 2>&1; then
        info "  ✓ Grafana API is healthy"
        break
    else
        ((retry_count++)) || true
        if [[ $retry_count -lt $max_retries ]]; then
            warn "  Retry $retry_count/$max_retries: Grafana not ready yet, waiting..."
            sleep 5
        else
            err "Grafana API health check failed after $max_retries retries"
            exit 1
        fi
    fi
done

echo ""
echo -e "${GREEN}=== Core + Observability Profile E2E Test PASSED ===${NC}"
echo ""

exit 0
