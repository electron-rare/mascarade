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
  doctor-mcp             Verify the KiCad MCP server loads and lists tools
  smoke                  Quick end-to-end health check (doctor + doctor-mcp)
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

  compose exec -T \
    -e HOME=/workspace/.cad-home/freecad-headless-root \
    -e LANG=C.UTF-8 \
    -e LC_ALL=C.UTF-8 \
    freecad-headless \
    sh -lc 'set -e; mkdir -p "$HOME"; if command -v FreeCADCmd >/dev/null 2>&1; then FreeCADCmd -c "import FreeCAD; print(\".\".join(FreeCAD.Version()[:3]))"; else freecadcmd -c "import FreeCAD; print(\".\".join(FreeCAD.Version()[:3]))"; fi'

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
  compose exec -T \
    -e HOME=/workspace/.cad-home/freecad-headless-root \
    -e LANG=C.UTF-8 \
    -e LC_ALL=C.UTF-8 \
    freecad-headless \
    sh -lc 'set -e; mkdir -p "$HOME"; if command -v FreeCADCmd >/dev/null 2>&1; then exec FreeCADCmd "$@"; else exec freecadcmd "$@"; fi' sh "$@"
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

doctor_mcp_cmd() {
  local status=0

  # Check that the kicad-mcp image builds / exists
  if ! compose build kicad-mcp >/dev/null 2>&1; then
    printf 'FAIL  kicad-mcp  image build failed\n'
    return 1
  fi

  # Check that node + dist/index.js exist in the image
  local version
  version=$(compose run --rm --no-deps -T \
    -e HOME=/tmp \
    kicad-mcp \
    sh -c 'node --version 2>/dev/null && test -f /opt/kicad-mcp/dist/index.js && echo "entrypoint:ok"' 2>&1) || true

  if echo "$version" | grep -q "entrypoint:ok"; then
    local node_ver
    node_ver=$(echo "$version" | head -1)
    printf 'OK    kicad-mcp  node %s, entrypoint present\n' "$node_ver"
  else
    printf 'FAIL  kicad-mcp  node or dist/index.js missing\n'
    status=1
  fi

  # Check that the MCP server responds to an initialize handshake (JSON-RPC over stdin)
  local init_response
  init_response=$(printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0.1"}}}\n' | \
    compose run --rm --no-deps -T \
      -e HOME=/tmp \
      kicad-mcp \
      sh -c 'cd /opt/kicad-mcp && timeout 10 node dist/index.js --stdio 2>/dev/null || true' 2>&1) || true

  if echo "$init_response" | grep -q '"serverInfo"'; then
    local server_name
    server_name=$(echo "$init_response" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    printf 'OK    kicad-mcp  MCP server responds (%s)\n' "${server_name:-unknown}"
  else
    printf 'FAIL  kicad-mcp  MCP server did not respond to initialize\n'
    debug "Response: $init_response"
    status=1
  fi

  return "$status"
}

smoke_cmd() {
  local status=0
  local failures=""

  log "Running CAD smoke test..."
  echo ""

  # 1. Doctor: tool versions
  log "Checking container tools..."
  if doctor_cmd; then
    printf 'OK    doctor     all container tools available\n'
  else
    printf 'FAIL  doctor     one or more container tools missing\n'
    failures="${failures}doctor "
    status=1
  fi
  echo ""

  # 2. Doctor MCP
  log "Checking MCP server..."
  if doctor_mcp_cmd; then
    : # status already printed
  else
    failures="${failures}mcp "
    status=1
  fi
  echo ""

  # 3. KiCad plugin doctor (host-side)
  log "Checking KiCad plugins (host)..."
  if "$ROOT_DIR/scripts/install_kicad_plugins.sh" doctor all 2>/dev/null; then
    : # status already printed
  else
    printf 'WARN  plugins    host KiCad plugins not installed (non-blocking)\n'
    # Not a hard failure — plugins may not be installed on this host
  fi
  echo ""

  # Summary
  if [ "$status" -eq 0 ]; then
    log "Smoke test PASSED"
  else
    log "Smoke test FAILED: ${failures}"
  fi

  return "$status"
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
  doctor-mcp)
    doctor_mcp_cmd
    ;;
  smoke)
    smoke_cmd
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
