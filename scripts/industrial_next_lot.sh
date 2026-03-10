#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AFC_DIR="${AFC_DIR:-/home/clems/agent-factory-cockpit}"
DEFAULT_LOT="dcs-governed-sandbox"

usage() {
  cat <<'EOF'
Usage: scripts/industrial_next_lot.sh <command> [lot]

Commands:
  status            Show the current next useful industrial lot
  plan [lot]        Print the VM integration plan for the lot
  verify [lot]      Rebuild/check the VM surfaces for the lot
  run [lot]         Run the upstream lot demo plus VM checks
  help              Show this message

Supported lots:
  dcs-governed-sandbox
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

lot_name() {
  local lot="${1:-$DEFAULT_LOT}"
  case "$lot" in
    dcs-governed-sandbox) printf '%s\n' "$lot" ;;
    *) die "unknown lot: $lot" ;;
  esac
}

plan_lot() {
  local lot
  lot="$(lot_name "${1:-}")"
  case "$lot" in
    dcs-governed-sandbox)
      cat <<'EOF'
Lot: dcs-governed-sandbox
VM integration:
  - rebuild core + agent-factory-cockpit + agent-factory-dcs-sandbox
  - keep industrial cockpit healthy behind edge-proxy
  - confirm /api/industrial/platform shows DCS configured on generic-rest api-key
  - keep /api/ops/summary coherent

Canonical checks:
  - docker compose config -q
  - docker compose up -d --build core agent-factory-cockpit agent-factory-dcs-sandbox
  - cd api && npm run test -- src/routes/industrial.test.ts src/routes/ops.test.ts
  - cd api && npm run build
  - cd web && npm run build:api-public
  - curl authenticated /api/industrial/platform
  - curl authenticated /api/ops/summary
EOF
      ;;
  esac
}

run_verify() {
  local lot
  lot="$(lot_name "${1:-}")"
  case "$lot" in
    dcs-governed-sandbox)
      (
        cd "$ROOT_DIR"
        docker compose config -q
        docker compose up -d --build core agent-factory-cockpit agent-factory-dcs-sandbox
        (cd api && npm run test -- src/routes/industrial.test.ts src/routes/ops.test.ts)
        (cd api && npm run build)
        (cd web && npm run build:api-public)
      )
      ;;
  esac
}

run_lot() {
  local lot
  lot="$(lot_name "${1:-}")"
  "$AFC_DIR/scripts/industrial_lot.sh" demo "$lot"
  run_verify "$lot"
}

command="${1:-help}"
lot="${2:-$DEFAULT_LOT}"

case "$command" in
  status)
    printf 'next_useful_lot=%s\n' "$DEFAULT_LOT"
    ;;
  plan)
    plan_lot "$lot"
    ;;
  verify)
    run_verify "$lot"
    ;;
  run)
    run_lot "$lot"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
