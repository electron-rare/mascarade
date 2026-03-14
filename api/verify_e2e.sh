#!/bin/bash
# Simple E2E verification script with full response output
# This demonstrates the complete pipeline API workflow

set -e

API_URL="http://localhost:3000"
API_PID=""

echo "=========================================="
echo "Pipeline API E2E Verification"
echo "=========================================="
echo ""

# Start API server
echo "Starting API server..."
cd "$(dirname "$0")"
npm run build > /dev/null 2>&1
node dist/index.js > api-verify.log 2>&1 &
API_PID=$!

# Wait for server
echo "Waiting for server to start..."
sleep 3

echo ""
echo "1. Testing POST /api/pipeline/run (dry_run=true)"
echo "   Request: {\"domain\":\"stm32\",\"dry_run\":true}"
echo ""
response1=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"domain":"stm32","dry_run":true}' \
  "$API_URL/api/pipeline/run")
echo "   Response:"
echo "$response1" | python3 -m json.tool
echo ""

# Wait for pipeline to run
echo "2. Waiting 2 seconds for pipeline to process..."
sleep 2
echo ""

echo "3. Testing GET /api/pipeline/status"
echo ""
response2=$(curl -s "$API_URL/api/pipeline/status")
echo "   Response:"
echo "$response2" | python3 -m json.tool
echo ""

echo "4. Testing GET /api/pipeline/models"
echo ""
response3=$(curl -s "$API_URL/api/pipeline/models")
echo "   Response:"
echo "$response3" | python3 -m json.tool | head -50
echo ""

# Cleanup
echo "Cleaning up..."
kill $API_PID 2>/dev/null || true
rm -f api-verify.log
rm -f ../finetune/state.json

echo ""
echo "=========================================="
echo "✓ E2E Verification Complete"
echo "=========================================="
