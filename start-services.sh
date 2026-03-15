#!/bin/bash

# Helper script to start all services for E2E testing

set -e

echo "Starting Mascarade services for E2E testing..."
echo ""

# Create log directory
mkdir -p /tmp/claude/mascarade-logs

# Kill any existing services on the ports
echo "Checking for existing services..."
lsof -ti:8100 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

sleep 2

# Start core service
echo "Starting Core service on port 8100..."
cd core
nohup python -m uvicorn mascarade.server:app --host 0.0.0.0 --port 8100 > /tmp/claude/mascarade-logs/core.log 2>&1 &
CORE_PID=$!
echo "Core PID: $CORE_PID"
cd ..

# Start API service
echo "Starting API service on port 3000..."
cd api
nohup npm run dev > /tmp/claude/mascarade-logs/api.log 2>&1 &
API_PID=$!
echo "API PID: $API_PID"
cd ..

# Start web service
echo "Starting Web service on port 5173..."
cd web
nohup npm run dev > /tmp/claude/mascarade-logs/web.log 2>&1 &
WEB_PID=$!
echo "Web PID: $WEB_PID"
cd ..

# Save PIDs
echo "$CORE_PID $API_PID $WEB_PID" > /tmp/claude/mascarade-logs/pids.txt

echo ""
echo "Waiting for services to start..."
sleep 10

# Check if services are responding
echo ""
echo "Checking service health..."

if curl -s http://localhost:8100/health > /dev/null 2>&1; then
    echo "✓ Core service is running (http://localhost:8100)"
else
    echo "✗ Core service failed to start"
    echo "Check logs: /tmp/claude/mascarade-logs/core.log"
fi

if curl -s http://localhost:3000/health > /dev/null 2>&1; then
    echo "✓ API service is running (http://localhost:3000)"
else
    echo "✗ API service failed to start"
    echo "Check logs: /tmp/claude/mascarade-logs/api.log"
fi

if curl -s -I http://localhost:5173/ > /dev/null 2>&1; then
    echo "✓ Web service is running (http://localhost:5173)"
else
    echo "✗ Web service failed to start"
    echo "Check logs: /tmp/claude/mascarade-logs/web.log"
fi

echo ""
echo "Services started! PIDs saved to /tmp/claude/mascarade-logs/pids.txt"
echo "Logs are in /tmp/claude/mascarade-logs/"
echo ""
echo "To stop services, run: ./stop-services.sh"
echo "Or manually: kill $CORE_PID $API_PID $WEB_PID"
echo ""
