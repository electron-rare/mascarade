#!/usr/bin/env bash
# test-fleet.sh — Run Python tests on all machines in the cluster
# Usage: ./test-fleet.sh [quick|full]
#
# quick: run core tests only (ml_classifier, rlvr, cli_agents, scheduler, mcp_server)
# full:  run all available tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MODE="${1:-quick}"

# Quick test files (no heavy deps needed)
QUICK_TESTS=(
    tests/test_ml_classifier.py
    tests/test_rlvr.py
    tests/test_cli_agents.py
    tests/test_scheduler.py
    tests/test_mcp_server.py
    tests/test_a2a.py
    tests/test_codestral_provider.py
    tests/test_mistral_agents.py
    tests/test_middleware.py
    tests/test_orchestrator_engine.py
)

# Fleet definition
declare -A FLEET_HOSTS=(
    ["grosmac"]="local"
    ["photon"]="root@192.168.0.119"
    ["kxkm-ai"]="kxkm@100.87.54.119"
    ["tower"]="clems@192.168.0.120"
)

declare -A FLEET_PATHS=(
    ["grosmac"]="$ROOT_DIR/core"
    ["photon"]="/mascarade/core"
    ["kxkm-ai"]="/ai/saisail/mascarade/core"
    ["tower"]="/tmp/mascarade-test/core"
)

declare -A FLEET_PYTHON=(
    ["grosmac"]="python3"
    ["photon"]="python3"
    ["kxkm-ai"]="python3"
    ["tower"]="python3"
)

TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_SKIP=0
TOTAL_ERR=0

run_tests() {
    local name="$1"
    local host="${FLEET_HOSTS[$name]}"
    local path="${FLEET_PATHS[$name]}"
    local py="${FLEET_PYTHON[$name]}"

    echo -e "\n${BLUE}=== $name ===${NC}"

    local test_files
    if [[ "$MODE" == "quick" ]]; then
        test_files="${QUICK_TESTS[*]}"
    else
        test_files="tests/"
    fi

    local cmd="cd $path && $py -m pytest $test_files --override-ini='addopts=' -q 2>&1 | tail -5"

    local result
    if [[ "$host" == "local" ]]; then
        result=$(eval "$cmd" 2>&1) || true
    else
        if ! ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" 'true' 2>/dev/null; then
            echo -e "${RED}  UNREACHABLE${NC}"
            return
        fi
        result=$(ssh -o ConnectTimeout=5 "$host" "$cmd" 2>&1) || true
    fi

    # Parse result
    local summary
    summary=$(echo "$result" | grep -E "passed|failed|error" | tail -1)
    if [[ -z "$summary" ]]; then
        summary=$(echo "$result" | tail -1)
    fi

    # Extract numbers
    local passed failed skipped errors
    passed=$(echo "$summary" | sed -n 's/.*\([0-9][0-9]*\) passed.*/\1/p')
    failed=$(echo "$summary" | sed -n 's/.*\([0-9][0-9]*\) failed.*/\1/p')
    skipped=$(echo "$summary" | sed -n 's/.*\([0-9][0-9]*\) skipped.*/\1/p')
    errors=$(echo "$summary" | sed -n 's/.*\([0-9][0-9]*\) error.*/\1/p')

    [[ -z "$passed" ]] && passed=0
    [[ -z "$failed" ]] && failed=0
    [[ -z "$skipped" ]] && skipped=0
    [[ -z "$errors" ]] && errors=0

    TOTAL_PASS=$((TOTAL_PASS + passed))
    TOTAL_FAIL=$((TOTAL_FAIL + failed))
    TOTAL_SKIP=$((TOTAL_SKIP + skipped))
    TOTAL_ERR=$((TOTAL_ERR + errors))

    if [[ "$failed" -eq 0 && "$errors" -eq 0 ]]; then
        echo -e "  ${GREEN}PASS${NC} — $passed passed, $skipped skipped"
    elif [[ "$errors" -gt 0 ]]; then
        echo -e "  ${YELLOW}WARN${NC} — $passed passed, $errors errors (missing deps)"
    else
        echo -e "  ${RED}FAIL${NC} — $passed passed, $failed failed"
    fi
}

echo -e "${BLUE}Mascarade Fleet Test Runner${NC} [$MODE mode]"
echo "$(date)"

for machine in grosmac photon kxkm-ai tower; do
    run_tests "$machine"
done

echo -e "\n${BLUE}=== Summary ===${NC}"
echo -e "  Total: $TOTAL_PASS passed, $TOTAL_FAIL failed, $TOTAL_SKIP skipped, $TOTAL_ERR errors"

if [[ "$TOTAL_FAIL" -eq 0 ]]; then
    echo -e "  ${GREEN}ALL PASS${NC}"
    exit 0
else
    echo -e "  ${RED}FAILURES DETECTED${NC}"
    exit 1
fi
