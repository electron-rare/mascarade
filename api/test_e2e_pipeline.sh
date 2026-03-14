#!/bin/bash
# End-to-End Test Script for Pipeline API Endpoints
# Tests: POST /api/pipeline/run, GET /api/pipeline/status, GET /api/pipeline/models

set -e

API_URL="http://localhost:3000"
API_PID=""
CLEANUP_DONE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "Pipeline API E2E Test"
echo "================================================"

# Cleanup function
cleanup() {
  if [ "$CLEANUP_DONE" = true ]; then
    return
  fi
  CLEANUP_DONE=true

  echo ""
  echo -e "${YELLOW}Cleaning up...${NC}"

  if [ -n "$API_PID" ]; then
    echo "Stopping API server (PID: $API_PID)..."
    kill $API_PID 2>/dev/null || true
    wait $API_PID 2>/dev/null || true
  fi

  # Clean up state file if it was created by dry-run
  if [ -f "../finetune/state.json" ]; then
    echo "Cleaning up state file..."
    rm -f "../finetune/state.json"
  fi

  # Clean up log file
  if [ -f "./api-test.log" ]; then
    echo "Cleaning up log file..."
    rm -f "./api-test.log"
  fi

  echo -e "${GREEN}Cleanup complete${NC}"
}

# Trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

# Function to check if server is ready
wait_for_server() {
  echo -n "Waiting for API server to be ready"
  for i in {1..30}; do
    if curl -s "$API_URL/api/health" > /dev/null 2>&1; then
      echo ""
      echo -e "${GREEN}✓ API server is ready${NC}"
      return 0
    fi
    echo -n "."
    sleep 1
  done
  echo ""
  echo -e "${RED}✗ API server failed to start${NC}"
  return 1
}

# Function to test endpoint
test_endpoint() {
  local name="$1"
  local method="$2"
  local endpoint="$3"
  local data="$4"
  local expected_status="$5"

  echo ""
  echo "Testing: $name"
  echo "  Method: $method"
  echo "  Endpoint: $endpoint"

  if [ -n "$data" ]; then
    response=$(curl -s -w "\n%{http_code}" -X "$method" \
      -H "Content-Type: application/json" \
      -d "$data" \
      "$API_URL$endpoint")
  else
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint")
  fi

  # Split response and status code
  status_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')

  echo "  Status: $status_code"
  echo "  Response: $body" | head -c 200

  if [ "$status_code" = "$expected_status" ]; then
    echo -e "  ${GREEN}✓ PASS${NC}"
    echo "$body"
    return 0
  else
    echo -e "  ${RED}✗ FAIL (expected $expected_status, got $status_code)${NC}"
    return 1
  fi
}

echo ""
echo "Step 1: Starting API server..."
cd "$(dirname "$0")"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
  echo "Installing npm dependencies..."
  npm install
fi

# Build the API first
echo "Building API..."
npm run build

# Start API server in background using built version
LOG_FILE="./api-test.log"
node dist/index.js > "$LOG_FILE" 2>&1 &
API_PID=$!
echo "API server started with PID: $API_PID"

# Wait for server to be ready
if ! wait_for_server; then
  echo "Server logs:"
  cat "$LOG_FILE" 2>/dev/null || echo "No log file found"
  exit 1
fi

# Run tests
echo ""
echo "================================================"
echo "Running E2E Tests"
echo "================================================"

TESTS_PASSED=0
TESTS_FAILED=0

# Test 1: POST /api/pipeline/run with dry_run=true
echo ""
echo "Test 1: Trigger pipeline in dry-run mode"
if test_endpoint \
  "POST /api/pipeline/run" \
  "POST" \
  "/api/pipeline/run" \
  '{"domain":"stm32","dry_run":true}' \
  "200"; then
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Wait a moment for pipeline to start
echo ""
echo "Waiting 3 seconds for pipeline to initialize..."
sleep 3

# Test 2: GET /api/pipeline/status
echo ""
echo "Test 2: Check pipeline status"
if status_response=$(test_endpoint \
  "GET /api/pipeline/status" \
  "GET" \
  "/api/pipeline/status" \
  "" \
  "200"); then
  TESTS_PASSED=$((TESTS_PASSED + 1))

  # Check if status contains expected data
  if echo "$status_response" | grep -q '"ok":true'; then
    echo -e "  ${GREEN}✓ Status response contains ok:true${NC}"
  else
    echo -e "  ${YELLOW}⚠ Status response missing ok:true${NC}"
  fi
else
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 3: GET /api/pipeline/models
echo ""
echo "Test 3: List fine-tuned models"
if models_response=$(test_endpoint \
  "GET /api/pipeline/models" \
  "GET" \
  "/api/pipeline/models" \
  "" \
  "200"); then
  TESTS_PASSED=$((TESTS_PASSED + 1))

  # Check if models response contains expected structure
  if echo "$models_response" | grep -q '"ok":true'; then
    echo -e "  ${GREEN}✓ Models response contains ok:true${NC}"
  else
    echo -e "  ${YELLOW}⚠ Models response missing ok:true${NC}"
  fi

  # Check if models data is present
  if echo "$models_response" | grep -q '"data"'; then
    echo -e "  ${GREEN}✓ Models response contains data field${NC}"
  else
    echo -e "  ${YELLOW}⚠ Models response missing data field${NC}"
  fi
else
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 4: POST /api/pipeline/run with invalid domain
echo ""
echo "Test 4: Trigger pipeline with invalid domain (should fail)"
if test_endpoint \
  "POST /api/pipeline/run (invalid)" \
  "POST" \
  "/api/pipeline/run" \
  '{"domain":"invalid_domain","dry_run":true}' \
  "400"; then
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Summary
echo ""
echo "================================================"
echo "Test Summary"
echo "================================================"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
  echo -e "${GREEN}✓ All E2E tests passed!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some tests failed${NC}"
  exit 1
fi
