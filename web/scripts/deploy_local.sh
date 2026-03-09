#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.local.yml"
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: web/scripts/deploy_local.sh <command> [options]

Commands:
  up            Build and start the local Crazy Life container
  down          Stop the local Crazy Life container
  build         Build the local Crazy Life image
  logs          Tail the local Crazy Life logs
  ps            Show the local Crazy Life container status
  url           Print the local URL
  help          Show this help

Environment:
  CRAZY_LIFE_BIND_HOST    Bind host for the local container (default: 127.0.0.1)
  CRAZY_LIFE_PORT         Published port (default: 8088)
  CRAZY_LIFE_API_ORIGIN   Upstream API origin for /api and /health (default: http://host.docker.internal:3100)
  CRAZY_LIFE_PROXY_ORIGIN Upstream proxy origin for /core-health and /dify-health (default: http://host.docker.internal)
  CRAZY_LIFE_BASE         Vite base path baked at build time (default: /)
EOF
}

log() {
  printf '[crazy-life-local] %s\n' "$*" >&2
}

debug() {
  if [[ "$VERBOSE" -eq 1 ]]; then
    printf '[crazy-life-local][dbg] %s\n' "$*" >&2
  fi
}

compose() {
  debug "docker compose -f $COMPOSE_FILE $*"
  docker compose -f "$COMPOSE_FILE" "$@"
}

cmd="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$cmd" in
  up)
    compose up -d --build
    log "crazy_life local URL: http://${CRAZY_LIFE_BIND_HOST:-127.0.0.1}:${CRAZY_LIFE_PORT:-8088}"
    ;;
  down)
    compose down
    ;;
  build)
    compose build
    ;;
  logs)
    compose logs -f
    ;;
  ps)
    compose ps
    ;;
  url)
    printf 'http://%s:%s\n' "${CRAZY_LIFE_BIND_HOST:-127.0.0.1}" "${CRAZY_LIFE_PORT:-8088}"
    ;;
  help)
    usage
    ;;
  *)
    printf 'Unknown command: %s\n' "$cmd" >&2
    usage >&2
    exit 2
    ;;
esac

