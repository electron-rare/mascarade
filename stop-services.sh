#!/bin/bash

# Helper script to stop all services

echo "Stopping Mascarade services..."

if [ -f /tmp/claude/mascarade-logs/pids.txt ]; then
    PIDS=$(cat /tmp/claude/mascarade-logs/pids.txt)
    for PID in $PIDS; do
        if kill -0 $PID 2>/dev/null; then
            echo "Killing process $PID"
            kill $PID 2>/dev/null || true
        fi
    done
    rm /tmp/claude/mascarade-logs/pids.txt
fi

# Also try to kill by port
lsof -ti:8100 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

echo "Services stopped."
