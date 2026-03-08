#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="${ROOT_DIR}/core"
VENV_DIR="${CORE_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BOOTSTRAP=false
PYTEST_ARGS=()

usage() {
  cat <<'EOF'
Usage: bash scripts/test_python.sh [options] [-- <pytest args>]

Run the supported mascarade/core Python test suite through the repo-local venv.

Options:
  --bootstrap        Create/install the venv first if missing
  --python BIN       Python interpreter forwarded to bootstrap if needed
  --venv-dir PATH    Virtualenv directory to use (default: core/.venv)
  -h, --help         Show this help

Examples:
  bash scripts/test_python.sh
  bash scripts/test_python.sh --bootstrap
  bash scripts/test_python.sh --venv-dir /tmp/mascarade-core-venv --bootstrap -- -k provider_admin
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bootstrap)
      BOOTSTRAP=true
      ;;
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
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      PYTEST_ARGS+=("$@")
      break
      ;;
    *)
      PYTEST_ARGS+=("$1")
      ;;
  esac
  shift
done

if [[ ! -x "${VENV_DIR}/bin/python" ]] || [[ ! -x "${VENV_DIR}/bin/pytest" ]]; then
  if [[ "${BOOTSTRAP}" == true ]]; then
    bash "${ROOT_DIR}/scripts/bootstrap_python_env.sh" --python "${PYTHON_BIN}" --venv-dir "${VENV_DIR}"
  else
    echo "Missing ${VENV_DIR} with pytest. Run: bash scripts/bootstrap_python_env.sh --venv-dir ${VENV_DIR}" >&2
    exit 1
  fi
fi

export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

cd "${CORE_DIR}"
exec "${VENV_DIR}/bin/python" -m pytest -q "${PYTEST_ARGS[@]}"
