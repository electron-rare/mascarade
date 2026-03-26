#!/usr/bin/env bash
# Run pytest with coverage and open the HTML report.
# Usage: ./scripts/coverage.sh [extra pytest args...]
set -euo pipefail

CORE_DIR="$(cd "$(dirname "$0")/../core" && pwd)"
cd "$CORE_DIR"

echo "Running pytest with coverage..."
.venv/bin/python -m pytest tests/ \
    --cov=mascarade \
    --cov-report=term \
    --cov-report=html:htmlcov \
    --cov-fail-under=40 \
    --ignore=tests/test_google_provider.py \
    --ignore=tests/node_engine \
    --ignore=tests/test_node_engine_runtime.py \
    "$@"

echo ""
echo "HTML coverage report: $CORE_DIR/htmlcov/index.html"

# Open the report (macOS)
if command -v open &>/dev/null; then
    open "$CORE_DIR/htmlcov/index.html"
elif command -v xdg-open &>/dev/null; then
    xdg-open "$CORE_DIR/htmlcov/index.html"
else
    echo "Open $CORE_DIR/htmlcov/index.html in your browser."
fi
