#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/deploy/apple_llm_api"
VENV_DIR="${APPLE_LLM_VENV_DIR:-${REPO_DIR}/.venv-apple-llm}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND="$(printf '%s' "${APPLE_LLM_BACKEND:-coreml}" | tr '[:upper:]' '[:lower:]')"
HOST="${APPLE_LLM_HOST:-127.0.0.1}"
PORT="${APPLE_LLM_PORT:-8201}"
STATE_FILE="${VENV_DIR}/.apple-llm-backend"

case "$BACKEND" in
  coreml)
    REQUIREMENTS_FILE="${APP_DIR}/requirements-coreml.txt"
    ;;
  onnx-coreml|ort-coreml)
    REQUIREMENTS_FILE="${APP_DIR}/requirements-onnx.txt"
    ;;
  *)
    echo "Unsupported APPLE_LLM_BACKEND: $BACKEND" >&2
    exit 2
    ;;
esac

need_install=false

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --upgrade pip
  need_install=true
elif [[ ! -f "${STATE_FILE}" ]] || [[ "$(cat "${STATE_FILE}")" != "${BACKEND}" ]]; then
  need_install=true
elif [[ "${APPLE_LLM_INSTALL_DEPS:-false}" == "true" ]]; then
  need_install=true
fi

if [[ "${need_install}" == "true" ]]; then
  "${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS_FILE}"
  printf '%s\n' "${BACKEND}" > "${STATE_FILE}"
fi

exec "${VENV_DIR}/bin/python" -m uvicorn app:app \
  --app-dir "${APP_DIR}" \
  --host "${HOST}" \
  --port "${PORT}"
