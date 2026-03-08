#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="${ROOT_DIR}/core"
VENV_DIR="${CORE_DIR}/.venv"

if [[ ! -x "${VENV_DIR}/bin/python" ]] || [[ ! -x "${VENV_DIR}/bin/pytest" ]]; then
  echo "Missing ${VENV_DIR} with pytest. Run: bash scripts/bootstrap_python_env.sh" >&2
  exit 1
fi

export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

cd "${CORE_DIR}"
exec "${VENV_DIR}/bin/python" -m pytest -q "$@"
