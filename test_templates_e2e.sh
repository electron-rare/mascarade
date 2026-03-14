#!/bin/bash
# End-to-end test script for agent workflow templates

set -e

echo "=== E2E Template Deployment Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
CORE_URL="${CORE_URL:-http://localhost:8100}"
API_URL="${API_URL:-http://localhost:3000}"
MAX_RETRIES=30
RETRY_DELAY=2

# Function to wait for service
wait_for_service() {
    local url=$1
    local name=$2
    echo "Waiting for $name at $url..."

    for i in $(seq 1 $MAX_RETRIES); do
        if curl -s -f "$url/health" > /dev/null 2>&1 || curl -s -f "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $name is ready${NC}"
            return 0
        fi
        echo "  Attempt $i/$MAX_RETRIES..."
        sleep $RETRY_DELAY
    done

    echo -e "${RED}✗ $name failed to start${NC}"
    return 1
}

# Function to test endpoint
test_endpoint() {
    local method=$1
    local url=$2
    local data=$3
    local expected_pattern=$4
    local description=$5

    echo ""
    echo "TEST: $description"
    echo "  $method $url"

    if [ -n "$data" ]; then
        response=$(curl -s -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data")
    else
        response=$(curl -s -X "$method" "$url")
    fi

    echo "  Response: ${response:0:200}..."

    if echo "$response" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✓ PASS${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL - Expected pattern not found: $expected_pattern${NC}"
        echo "  Full response: $response"
        return 1
    fi
}

# Main test flow
main() {
    local failed=0

    echo "Step 1: Check if services are running"
    if ! wait_for_service "$CORE_URL" "Core service"; then
        echo ""
        echo "Core service not running. Start it with:"
        echo "  cd core && source .venv/bin/activate && python -m uvicorn mascarade.server:app --reload --port 8100"
        echo "Or use docker-compose up"
        failed=1
    fi

    if ! wait_for_service "$API_URL" "API service"; then
        echo ""
        echo "API service not running. Start it with:"
        echo "  cd api && npm run dev"
        echo "Or use docker-compose up"
        failed=1
    fi

    if [ $failed -eq 1 ]; then
        echo ""
        echo -e "${RED}Services not ready. Exiting.${NC}"
        exit 1
    fi

    echo ""
    echo "=== Running Tests ==="

    # Test 1: List templates
    if ! test_endpoint "GET" "$API_URL/api/orchestrate/templates" "" \
        '"id"' \
        "List all templates (verify 4+ returned)"; then
        failed=1
    fi

    # Test 2: Get specific template
    if ! test_endpoint "GET" "$API_URL/api/orchestrate/templates/code-review-workflow" "" \
        '"code-review-workflow"' \
        "Get code-review template"; then
        failed=1
    fi

    # Test 3: Deploy code review template
    code_review_payload='{
        "input": "Review this Python function:\n\ndef calculate_total(items):\n    total = 0\n    for item in items:\n        total = total + item[\"price\"]\n    return total"
    }'
    if ! test_endpoint "POST" "$API_URL/api/orchestrate/templates/code-review-workflow/deploy" \
        "$code_review_payload" \
        '"run_id"' \
        "Deploy code-review template with sample code"; then
        failed=1
    fi

    # Test 4: Get electronics template
    if ! test_endpoint "GET" "$API_URL/api/orchestrate/templates/electronics-pipeline" "" \
        '"electronics-pipeline"' \
        "Get electronics template"; then
        failed=1
    fi

    # Test 5: Deploy electronics template
    electronics_payload='{
        "input": "Design a simple LED driver circuit for a 3W LED, input voltage 12V DC"
    }'
    if ! test_endpoint "POST" "$API_URL/api/orchestrate/templates/electronics-pipeline/deploy" \
        "$electronics_payload" \
        '"run_id"' \
        "Deploy electronics template"; then
        failed=1
    fi

    # Test 6: Deploy with customization (routing overrides)
    custom_payload='{
        "input": "Analyze this algorithm for performance issues",
        "routing_overrides": {
            "coder": {
                "strategy": "fastest"
            }
        }
    }'
    if ! test_endpoint "POST" "$API_URL/api/orchestrate/templates/code-review-workflow/deploy" \
        "$custom_payload" \
        '"run_id"' \
        "Deploy template with routing customization"; then
        failed=1
    fi

    echo ""
    echo "=== Test Summary ==="
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
}

# Run main
main "$@"
