#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="${ROOT_DIR}/core"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR_DEFAULT="${CORE_DIR}/.venv"
VENV_DIR="${VENV_DIR_DEFAULT}"
REINSTALL=false

usage() {
  cat <<'EOF'
Usage: bash scripts/bootstrap_python_env.sh [options]

Create or refresh the supported Python test environment for mascarade/core.

Options:
  --python BIN       Python interpreter to use (default: PYTHON_BIN or python3)
  --venv-dir PATH    Virtualenv directory to create/reuse (default: core/.venv)
  --reinstall        Remove and recreate the target virtualenv before install
  -h, --help         Show this help

Examples:
  bash scripts/bootstrap_python_env.sh
  bash scripts/bootstrap_python_env.sh --python python3.11
  bash scripts/bootstrap_python_env.sh --venv-dir /tmp/mascarade-core-venv --reinstall
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --python" >&2; usage >&2; exit 2; }
      PYTHON_BIN="$1"
      ;;
    --venv-dir)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --venv-dir" >&2; usage >&2; exit 2; }
      VENV_DIR="$1"
      ;;
    --reinstall)
      REINSTALL=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -d "${CORE_DIR}" ]]; then
  echo "Missing core directory: ${CORE_DIR}" >&2
  exit 1
fi

if [[ "${REINSTALL}" == true && -d "${VENV_DIR}" ]]; then
  echo "[bootstrap-python] removing ${VENV_DIR}"
  rm -rf "${VENV_DIR}"
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "[bootstrap-python] creating ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
  echo "[bootstrap-python] reusing ${VENV_DIR}"
fi

if [[ ! -x "${VENV_DIR}/bin/pytest" ]] || ! "${VENV_DIR}/bin/python" -c "import mascarade" >/dev/null 2>&1; then
  echo "[bootstrap-python] installing core test dependencies"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
  (
    cd "${CORE_DIR}"
    "${VENV_DIR}/bin/python" -m pip install -e ".[dev]"
  )
fi

echo "[bootstrap-python] python: ${VENV_DIR}/bin/python"
echo "[bootstrap-python] test:   bash scripts/test_python.sh --venv-dir ${VENV_DIR}"
