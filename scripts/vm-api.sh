#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.vm"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
else
  echo "Missing $ENV_FILE. Copy .env.vm.example to .env.vm first." >&2
  exit 1
fi

API_URL="${VM_API_URL:-http://192.168.0.119:3000}"
API_KEY="${MASCARADE_API_KEY:-}"
PATH_SUFFIX="${1:-/health}"

if [[ "$PATH_SUFFIX" != /* ]]; then
  PATH_SUFFIX="/$PATH_SUFFIX"
fi

if [[ -n "$API_KEY" ]]; then
  curl -sS -H "Authorization: Bearer ${API_KEY}" "${API_URL}${PATH_SUFFIX}"
else
  curl -sS "${API_URL}${PATH_SUFFIX}"
fi

echo
