#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="${ROOT_DIR}/core"
OPS_AGENT_REQ_FILE="${ROOT_DIR}/deploy/ops_agent/requirements.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR_DEFAULT="${CORE_DIR}/.venv"
VENV_DIR="${VENV_DIR_DEFAULT}"
STAMP_FILE=""
REINSTALL=false

usage_error() {
  echo "$1" >&2
  usage >&2
  exit 2
}

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

hash_files_sha256() {
  if [[ $# -eq 0 ]]; then
    return 1
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    cat "$@" 2>/dev/null | sha256sum | awk '{print $1}'
    return 0
  fi
  if command -v shasum >/dev/null 2>&1; then
    cat "$@" 2>/dev/null | shasum -a 256 | awk '{print $1}'
    return 0
  fi
  return 1
}

current_dep_signature() {
  local files=("${CORE_DIR}/pyproject.toml")
  if [[ -f "${OPS_AGENT_REQ_FILE}" ]]; then
    files+=("${OPS_AGENT_REQ_FILE}")
  fi
  hash_files_sha256 "${files[@]}"
}

venv_supports_repo_validation() {
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

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    --reinstall)
      REINSTALL=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage_error "Unknown option: $1"
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

STAMP_FILE="${VENV_DIR}/.mascarade_py_deps.sha256"

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

dep_sig="$(current_dep_signature || true)"
prev_sig=""
if [[ -f "${STAMP_FILE}" ]]; then
  prev_sig="$(cat "${STAMP_FILE}" 2>/dev/null || true)"
fi

if [[ ! -x "${VENV_DIR}/bin/pytest" ]] || ! venv_supports_repo_validation || [[ -n "${dep_sig}" && "${dep_sig}" != "${prev_sig}" ]]; then
  echo "[bootstrap-python] installing core test dependencies"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
  (
    cd "${CORE_DIR}"
    "${VENV_DIR}/bin/python" -m pip install -e ".[dev]"
  )
  if [[ -f "${OPS_AGENT_REQ_FILE}" ]]; then
    "${VENV_DIR}/bin/python" -m pip install -r "${OPS_AGENT_REQ_FILE}"
  fi
  if [[ -n "${dep_sig}" ]]; then
    echo "${dep_sig}" > "${STAMP_FILE}"
  fi
fi

if [[ ! -x "${VENV_DIR}/bin/pytest" ]] || ! venv_supports_repo_validation; then
  echo "[bootstrap-python] repo-local test environment is still incomplete after install" >&2
  exit 1
fi

echo "[bootstrap-python] python: ${VENV_DIR}/bin/python"
echo "[bootstrap-python] test:   bash scripts/test_python.sh --venv-dir ${VENV_DIR}"
