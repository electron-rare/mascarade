#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Build frontend
npm run build 2>/dev/null

# Start backend
pip install fastapi uvicorn 2>/dev/null
uvicorn server:app --host 0.0.0.0 --port 8200 --reload
