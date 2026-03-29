#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

if ! require_cmd docker; then
  exit 0
fi

qa_run "docker compose config" bash -lc "cd '$ROOT' && docker compose config >/dev/null"

if [[ -f "$ROOT/docker-compose.override.yml" ]]; then
  qa_run "docker compose config (override)" \
    bash -lc "cd '$ROOT' && docker compose -f docker-compose.yml -f docker-compose.override.yml config >/dev/null"
fi

echo "[OK] compose QA passed"
