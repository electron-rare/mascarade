#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="${ROOT_DIR}/core"
VENV_DIR="${CORE_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -d "${CORE_DIR}" ]]; then
  echo "Missing core directory: ${CORE_DIR}" >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "[bootstrap-python] creating ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

if [[ ! -x "${VENV_DIR}/bin/pytest" ]] || ! "${VENV_DIR}/bin/python" -c "import mascarade" >/dev/null 2>&1; then
  echo "[bootstrap-python] installing core test dependencies"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  (
    cd "${CORE_DIR}"
    "${VENV_DIR}/bin/python" -m pip install -e ".[dev]"
  )
else
  echo "[bootstrap-python] reusing ${VENV_DIR}"
fi

echo "[bootstrap-python] python: ${VENV_DIR}/bin/python"
echo "[bootstrap-python] test:   bash scripts/test_python.sh"
