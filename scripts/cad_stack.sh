#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/cad/docker-compose.yml"
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: cad_stack.sh <command> [args...]

Commands:
  up [services...]       Start CAD helper containers
  down                   Stop CAD helper containers
  ps                     Show CAD container status
  build [services...]    Build local CAD images
  doctor                 Print tool versions from the containers
  kicad-cli <args...>    Run kicad-cli in the headless container
  freecad-cmd <args...>  Run FreeCADCmd in the headless container
  pio <args...>          Run PlatformIO in the container
  mcp [args...]          Run the KiCad MCP server on stdio
  help                   Show this help

Environment:
  CAD_WORKSPACE_DIR      Workspace mounted at /workspace (default: repo root)
EOF
}

log() {
  printf '[cad] %s\n' "$*"
}

debug() {
  if [ "$VERBOSE" -eq 1 ]; then
    printf '[cad][dbg] %s\n' "$*" >&2
  fi
}

compose() {
  debug "docker compose -f $COMPOSE_FILE $*"
  docker compose -f "$COMPOSE_FILE" "$@"
}

ensure_service_up() {
  local service="$1"
  if ! compose ps --status running --services | grep -qx "$service"; then
    log "Starting $service"
    compose up -d "$service"
  fi
}

run_shell_as_host_user() {
  local service="$1"
  local home_dir="$2"
  shift 2
  local shell_command="$*"
  compose exec -T \
    --user "$(id -u):$(id -g)" \
    -e HOME="$home_dir" \
    "$service" \
    sh -lc "$shell_command"
}

run_tool_as_host_user() {
  local service="$1"
  local home_dir="$2"
  local prelude="$3"
  local binary="$4"
  shift 4
  compose exec -T \
    --user "$(id -u):$(id -g)" \
    -e HOME="$home_dir" \
    "$service" \
    sh -lc 'set -e; mkdir -p "$HOME"; '"$prelude"'; exec "$@"' sh "$binary" "$@"
}

build_cmd() {
  if [ "$#" -gt 0 ]; then
    compose build "$@"
  else
    compose build
  fi
}

up_cmd() {
  if [ "$#" -gt 0 ]; then
    compose up -d "$@"
    return
  fi

  compose up -d kicad-headless freecad-headless platformio
}

doctor_cmd() {
  ensure_service_up kicad-headless
  ensure_service_up freecad-headless
  ensure_service_up platformio

  run_shell_as_host_user \
    kicad-headless \
    /workspace/.cad-home/kicad-headless \
    'mkdir -p "$HOME" && kicad-cli version'

  run_shell_as_host_user \
    freecad-headless \
    /workspace/.cad-home/freecad-headless \
    'mkdir -p "$HOME" && FreeCADCmd -c "import FreeCAD; print(\".\".join(FreeCAD.Version()[:3]))"'

  run_shell_as_host_user \
    platformio \
    /workspace/.cad-home/platformio \
    'mkdir -p "$HOME" "$HOME/.platformio" && export PLATFORMIO_CORE_DIR="$HOME/.platformio" && pio --version'
}

kicad_cli_cmd() {
  ensure_service_up kicad-headless
  run_tool_as_host_user \
    kicad-headless \
    /workspace/.cad-home/kicad-headless \
    ":" \
    kicad-cli \
    "$@"
}

freecad_cmd() {
  ensure_service_up freecad-headless
  run_tool_as_host_user \
    freecad-headless \
    /workspace/.cad-home/freecad-headless \
    ":" \
    FreeCADCmd \
    "$@"
}

pio_cmd() {
  ensure_service_up platformio
  run_tool_as_host_user \
    platformio \
    /workspace/.cad-home/platformio \
    'mkdir -p "$HOME/.platformio"; export PLATFORMIO_CORE_DIR="$HOME/.platformio"' \
    pio \
    "$@"
}

mcp_cmd() {
  compose run --rm --no-deps -T \
    --user "$(id -u):$(id -g)" \
    -e HOME=/workspace/.cad-home/kicad-mcp \
    kicad-mcp \
    sh -lc 'set -e; mkdir -p "$HOME"; cd /opt/kicad-mcp; exec node dist/index.js "$@"' sh "$@"
}

while [ "$#" -gt 0 ]; do
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
      break
      ;;
  esac
done

cmd="${1:-help}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$cmd" in
  up)
    up_cmd "$@"
    ;;
  down)
    compose down
    ;;
  ps)
    compose ps
    ;;
  build)
    build_cmd "$@"
    ;;
  doctor)
    doctor_cmd
    ;;
  kicad-cli)
    if [ "$#" -eq 0 ]; then
      echo "cad_stack.sh kicad-cli: missing arguments" >&2
      exit 2
    fi
    kicad_cli_cmd "$@"
    ;;
  freecad-cmd)
    if [ "$#" -eq 0 ]; then
      echo "cad_stack.sh freecad-cmd: missing arguments" >&2
      exit 2
    fi
    freecad_cmd "$@"
    ;;
  pio)
    if [ "$#" -eq 0 ]; then
      echo "cad_stack.sh pio: missing arguments" >&2
      exit 2
    fi
    pio_cmd "$@"
    ;;
  mcp)
    mcp_cmd "$@"
    ;;
  help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
