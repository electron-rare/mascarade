#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="${ROOT_DIR}/core"
VENV_DIR="${CORE_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BOOTSTRAP=false
REINSTALL=false
PYTEST_ARGS=()

usage_error() {
  echo "$1" >&2
  usage >&2
  exit 2
}

venv_supports_repo_validation() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  [[ -x "${VENV_DIR}/bin/pytest" ]] || return 1
  (
    cd "${ROOT_DIR}"
    "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib

importlib.import_module("mascarade")
importlib.import_module("prometheus_client")
importlib.import_module("deploy.ops_agent.app")
PY
  )
}

usage() {
  cat <<'EOF'
Usage: bash scripts/test_python.sh [options] [-- <pytest args>]

Run the supported mascarade/core Python test suite through the repo-local venv.

Options:
  --bootstrap        Create/install the venv first if missing
  --reinstall        Recreate the venv before bootstrapping
  --python BIN       Python interpreter forwarded to bootstrap if needed
  --venv-dir PATH    Virtualenv directory to use (default: core/.venv)
  -h, --help         Show this help

Examples:
  bash scripts/test_python.sh
  bash scripts/test_python.sh --bootstrap
  bash scripts/test_python.sh --bootstrap --reinstall
  bash scripts/test_python.sh --venv-dir /tmp/mascarade-core-venv --bootstrap -- -k provider_admin
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bootstrap)
      BOOTSTRAP=true
      ;;
    --reinstall)
      BOOTSTRAP=true
      REINSTALL=true
      ;;
    --python)
      shift
      [[ $# -gt 0 ]] || usage_error "Missing value for --python"
      PYTHON_BIN="$1"
      ;;
    --venv-dir)
      shift
      [[ $# -gt 0 ]] || usage_error "Missing value for --venv-dir"
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

if ! venv_supports_repo_validation; then
  if [[ "${BOOTSTRAP}" == true ]]; then
    bootstrap_cmd=(
      bash
      "${ROOT_DIR}/scripts/bootstrap_python_env.sh"
      --python
      "${PYTHON_BIN}"
      --venv-dir
      "${VENV_DIR}"
    )
    if [[ "${REINSTALL}" == true ]]; then
      bootstrap_cmd+=(--reinstall)
    fi
    "${bootstrap_cmd[@]}"
  else
    echo "Incomplete ${VENV_DIR}. Run: bash scripts/bootstrap_python_env.sh --venv-dir ${VENV_DIR}" >&2
    exit 1
  fi
fi

export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

cd "${CORE_DIR}"
exec "${VENV_DIR}/bin/python" -m pytest -q "${PYTEST_ARGS[@]}"
