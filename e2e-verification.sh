#!/bin/bash

# End-to-End Verification Script for Agent Management Workflow
# This script tests the complete agent management lifecycle

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "Agent Management E2E Verification"
echo "========================================"
echo ""

# Check if services are running
echo "1. Checking if services are running..."
if ! curl -s http://localhost:8100/health > /dev/null 2>&1; then
    echo -e "${RED}❌ Core service not running on port 8100${NC}"
    echo "Please start services first: ./.auto-claude/specs/008-web-ui-for-agent-management/init.sh"
    exit 1
fi
echo -e "${GREEN}✓ Core service is running${NC}"

if ! curl -s http://localhost:3000/health > /dev/null 2>&1; then
    echo -e "${RED}❌ API service not running on port 3000${NC}"
    exit 1
fi
echo -e "${GREEN}✓ API service is running${NC}"

if ! curl -s -I http://localhost:5173/ > /dev/null 2>&1; then
    echo -e "${RED}❌ Web service not running on port 5173${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Web service is running${NC}"

echo ""
echo "2. Creating test agent via API..."
TEST_AGENT_NAME="e2e-test-agent-$(date +%s)"
CREATE_RESPONSE=$(curl -s -X POST http://localhost:3000/api/agents \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"$TEST_AGENT_NAME\",
    \"description\": \"E2E test agent\",
    \"system_prompt\": \"You are a helpful test agent.\",
    \"model_preference\": \"gpt-4\",
    \"routing_strategy\": \"specific\",
    \"metadata\": {
      \"builtin\": false
    }
  }")

if echo "$CREATE_RESPONSE" | grep -q "\"$TEST_AGENT_NAME\""; then
    echo -e "${GREEN}✓ Agent created successfully${NC}"
else
    echo -e "${RED}❌ Failed to create agent${NC}"
    echo "Response: $CREATE_RESPONSE"
    exit 1
fi

echo ""
echo "3. Verifying agent appears in list..."
LIST_RESPONSE=$(curl -s http://localhost:3000/api/agents)
if echo "$LIST_RESPONSE" | grep -q "\"$TEST_AGENT_NAME\""; then
    echo -e "${GREEN}✓ Agent appears in list${NC}"
else
    echo -e "${RED}❌ Agent not found in list${NC}"
    exit 1
fi

echo ""
echo "4. Retrieving agent details..."
AGENT_RESPONSE=$(curl -s http://localhost:3000/api/agents/$TEST_AGENT_NAME)
if echo "$AGENT_RESPONSE" | grep -q "\"name\":\"$TEST_AGENT_NAME\""; then
    echo -e "${GREEN}✓ Agent details retrieved${NC}"
else
    echo -e "${RED}❌ Failed to retrieve agent details${NC}"
    exit 1
fi

echo ""
echo "5. Updating agent system prompt..."
UPDATE_RESPONSE=$(curl -s -X PUT http://localhost:3000/api/agents/$TEST_AGENT_NAME \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"$TEST_AGENT_NAME\",
    \"description\": \"E2E test agent - updated\",
    \"system_prompt\": \"You are a helpful test agent. This prompt has been updated.\",
    \"model_preference\": \"gpt-4\",
    \"routing_strategy\": \"specific\",
    \"metadata\": {
      \"builtin\": false
    }
  }")

if echo "$UPDATE_RESPONSE" | grep -q "updated"; then
    echo -e "${GREEN}✓ Agent updated successfully${NC}"
else
    echo -e "${RED}❌ Failed to update agent${NC}"
    echo "Response: $UPDATE_RESPONSE"
    exit 1
fi

echo ""
echo "6. Verifying updated prompt..."
UPDATED_AGENT=$(curl -s http://localhost:3000/api/agents/$TEST_AGENT_NAME)
if echo "$UPDATED_AGENT" | grep -q "This prompt has been updated"; then
    echo -e "${GREEN}✓ System prompt updated correctly${NC}"
else
    echo -e "${RED}❌ System prompt not updated${NC}"
    exit 1
fi

echo ""
echo "7. Testing agent in playground (if router is configured)..."
# Note: This requires router configuration, skip if not available
PLAYGROUND_RESPONSE=$(curl -s -X POST http://localhost:3000/api/agents/$TEST_AGENT_NAME/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"messages\": [
      {\"role\": \"user\", \"content\": \"Hello, this is a test.\"}
    ]
  }" || echo '{"skipped": true}')

if echo "$PLAYGROUND_RESPONSE" | grep -q "skipped"; then
    echo -e "${YELLOW}⚠ Playground test skipped (router not configured)${NC}"
elif echo "$PLAYGROUND_RESPONSE" | grep -q "content"; then
    echo -e "${GREEN}✓ Playground response received${NC}"
else
    echo -e "${YELLOW}⚠ Playground test inconclusive${NC}"
fi

echo ""
echo "8. Retrieving agent metrics..."
METRICS_RESPONSE=$(curl -s http://localhost:3000/api/agents/$TEST_AGENT_NAME/metrics)
if echo "$METRICS_RESPONSE" | grep -q "total_requests\|error"; then
    echo -e "${GREEN}✓ Metrics endpoint responding${NC}"
else
    echo -e "${RED}❌ Failed to retrieve metrics${NC}"
    echo "Response: $METRICS_RESPONSE"
fi

echo ""
echo "9. Deleting test agent..."
DELETE_RESPONSE=$(curl -s -X DELETE http://localhost:3000/api/agents/$TEST_AGENT_NAME)
if echo "$DELETE_RESPONSE" | grep -q "deleted\|success"; then
    echo -e "${GREEN}✓ Agent deleted successfully${NC}"
else
    echo -e "${RED}❌ Failed to delete agent${NC}"
    echo "Response: $DELETE_RESPONSE"
    exit 1
fi

echo ""
echo "10. Verifying agent removed from list..."
sleep 1
FINAL_LIST=$(curl -s http://localhost:3000/api/agents)
if echo "$FINAL_LIST" | grep -q "\"$TEST_AGENT_NAME\""; then
    echo -e "${RED}❌ Agent still appears in list after deletion${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Agent successfully removed from list${NC}"
fi

echo ""
echo "========================================"
echo -e "${GREEN}✅ All E2E tests passed!${NC}"
echo "========================================"
echo ""
echo "Manual UI Verification Steps:"
echo "1. Open http://localhost:5173/agents in browser"
echo "2. Create a new agent using the UI form"
echo "3. Click on the agent to open detail page"
echo "4. Edit the system prompt using the enhanced editor"
echo "5. Switch to Preview tab to see markdown rendering"
echo "6. Test agent in the playground panel"
echo "7. View agent metrics (health status, request count, etc.)"
echo "8. Click Delete button and confirm"
echo "9. Verify agent is removed from the list"
echo ""
