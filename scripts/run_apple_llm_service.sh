#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/deploy/apple_llm_api"
BACKEND="$(printf '%s' "${APPLE_LLM_BACKEND:-coreml}" | tr '[:upper:]' '[:lower:]')"
HOST="${APPLE_LLM_HOST:-127.0.0.1}"
PORT="${APPLE_LLM_PORT:-8201}"

pick_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    printf '%s\n' "${PYTHON_BIN}"
    return
  fi

  if [[ "${BACKEND}" == "coreml" || "${BACKEND}" == "onnx-coreml" || "${BACKEND}" == "ort-coreml" ]]; then
    local candidate
    for candidate in \
      "${APPLE_LLM_COREML_PYTHON_BIN:-}" \
      /opt/homebrew/opt/python@3.12/bin/python3.12 \
      /usr/local/opt/python@3.12/bin/python3.12 \
      python3.12 \
      python3.11 \
      python3.10; do
      [[ -z "${candidate}" ]] && continue
      if command -v "${candidate}" >/dev/null 2>&1; then
        command -v "${candidate}"
        return
      fi
      if [[ -x "${candidate}" ]]; then
        printf '%s\n' "${candidate}"
        return
      fi
    done
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi

  printf '%s\n' python3
}

python_major_minor() {
  "$1" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'
}

PYTHON_BIN="$(pick_python_bin)"
PYTHON_VERSION="$(python_major_minor "${PYTHON_BIN}")"
PYTHON_MAJOR="${PYTHON_VERSION%%.*}"
PYTHON_MINOR="${PYTHON_VERSION##*.}"
VENV_DIR="${APPLE_LLM_VENV_DIR:-${REPO_DIR}/.venv-apple-llm-${BACKEND}-py${PYTHON_VERSION}}"
STATE_FILE="${VENV_DIR}/.apple-llm-backend"

if [[ "${BACKEND}" == "coreml" ]]; then
  if (( PYTHON_MAJOR > 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR > 12) )); then
    echo "APPLE_LLM_BACKEND=coreml requires Python 3.7-3.12 for coremltools wheels." >&2
    echo "Selected interpreter: ${PYTHON_BIN} (${PYTHON_VERSION})" >&2
    echo "Install python@3.12 and rerun, or set APPLE_LLM_COREML_PYTHON_BIN explicitly." >&2
    exit 2
  fi
fi

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
