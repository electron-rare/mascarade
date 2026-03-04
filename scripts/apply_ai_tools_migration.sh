#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_DIR="${1:-/home/cils/tools}"

echo "[migration] repo:   ${REPO_DIR}"
echo "[migration] target: ${TARGET_DIR}"

mkdir -p "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}/models"
mkdir -p "${TARGET_DIR}/python-tools"

cp "${REPO_DIR}/deploy/migration/compose.tools.ai.yml" "${TARGET_DIR}/docker-compose.ai.yml"
cp "${REPO_DIR}/deploy/migration/python-tools.requirements.txt" "${TARGET_DIR}/python-tools/requirements.txt"

if [[ -d "${TARGET_DIR}/python-tools/.venv" ]]; then
  echo "[migration] Python venv detected, installing requirements..."
  # shellcheck disable=SC1091
  source "${TARGET_DIR}/python-tools/.venv/bin/activate"
  python -m pip install -r "${TARGET_DIR}/python-tools/requirements.txt"
else
  echo "[migration] No python venv found at ${TARGET_DIR}/python-tools/.venv (skipped pip install)."
fi

echo ""
echo "[migration] Files copied:"
echo "  - ${TARGET_DIR}/docker-compose.ai.yml"
echo "  - ${TARGET_DIR}/python-tools/requirements.txt"
echo ""
echo "[migration] Start heavy AI services when needed:"
echo "  cd ${TARGET_DIR}"
echo "  docker compose -f docker-compose.yml -f docker-compose.ai.yml --profile heavy up -d localai koboldcpp anythingllm sglang"
echo ""
echo "[migration] Keep disabled on light machine (recommended):"
echo "  docker rm -f tools-localai tools-koboldcpp tools-anythingllm tools-sglang tools-mem0 tools-langfuse tools-clickhouse 2>/dev/null || true"

