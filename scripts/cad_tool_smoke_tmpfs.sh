#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CAD_STACK="$ROOT_DIR/scripts/cad_stack.sh"
DEFAULT_ROOT="/dev/shm/mascarade-cad-smoke"
KICAD_MCP_CONTEXT="$ROOT_DIR/finetune/kicad_mcp_server"

LABEL="cad-smoke"
WORKSPACE=""
RUN_DOCTOR=1
RUN_KICAD=1
RUN_KICAD_MCP=1
RUN_FREECAD=1
RUN_PLATFORMIO=1
KEEP_WORKSPACE=1
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: ./scripts/cad_tool_smoke_tmpfs.sh [options]

Run lightweight CAD/EDA tool smokes in a tmpfs-backed workspace.

Options:
  --label NAME         Label used for the tmpfs workspace (default: cad-smoke)
  --workspace PATH     Explicit workspace root (default: /dev/shm/mascarade-cad-smoke/<label>_<stamp>)
  --no-doctor          Skip `cad_stack.sh doctor`
  --skip-kicad         Skip KiCad CLI smoke
  --skip-kicad-mcp     Skip KiCad MCP stdio smoke
  --skip-freecad       Skip FreeCAD smoke
  --skip-platformio    Skip PlatformIO smoke
  --cleanup            Remove the tmpfs workspace after the run
  --verbose            Print executed commands
  -h, --help           Show this help
EOF
}

log() {
  printf '[cad-smoke] %s\n' "$*"
}

resolve_workspace() {
  local path="$1"
  local parent
  parent="$(dirname "$path")"
  mkdir -p "$parent"
  parent="$(cd "$parent" && pwd)"
  printf '%s/%s\n' "$parent" "$(basename "$path")"
}

jsonrpc_frame() {
  local body="$1"
  local length
  length="$(printf '%s' "$body" | wc -c | tr -d '[:space:]')"
  printf 'Content-Length: %s\r\n\r\n%s' "$length" "$body"
}

run_kicad_mcp_smoke() {
  local input_file="$WORKSPACE/kicad-smoke/mcp.input"
  local output_file="$WORKSPACE/kicad-smoke/mcp.output"
  local error_file="$WORKSPACE/kicad-smoke/mcp.error.log"

  {
    jsonrpc_frame '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"mascarade-cad-smoke","version":"0.1.0"}}}'
    jsonrpc_frame '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
    jsonrpc_frame '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
  } >"$input_file"

  if run timeout 20s "$CAD_STACK" mcp <"$input_file" >"$output_file" 2>"$error_file"; then
    :
  elif [ -s "$output_file" ] || grep -q '"serverInfo"' "$error_file" 2>/dev/null; then
    :
  else
    return 1
  fi

  grep -Eq '"serverInfo"|"tools"' "$output_file"
}

kicad_mcp_available() {
  [ -f "$KICAD_MCP_CONTEXT/package.json" ]
}

run() {
  if [ "$VERBOSE" -eq 1 ]; then
    printf '[cad-smoke][cmd] %s\n' "$*" >&2
  fi
  "$@"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --label)
      [ "$#" -ge 2 ] || { echo "--label requires a value" >&2; exit 2; }
      LABEL="$2"
      shift 2
      ;;
    --workspace)
      [ "$#" -ge 2 ] || { echo "--workspace requires a value" >&2; exit 2; }
      WORKSPACE="$2"
      shift 2
      ;;
    --no-doctor)
      RUN_DOCTOR=0
      shift
      ;;
    --skip-kicad)
      RUN_KICAD=0
      shift
      ;;
    --skip-kicad-mcp)
      RUN_KICAD_MCP=0
      shift
      ;;
    --skip-freecad)
      RUN_FREECAD=0
      shift
      ;;
    --skip-platformio)
      RUN_PLATFORMIO=0
      shift
      ;;
    --cleanup)
      KEEP_WORKSPACE=0
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ ! -x "$CAD_STACK" ]; then
  echo "Missing CAD helper: $CAD_STACK" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
if [ -z "$WORKSPACE" ]; then
  WORKSPACE="$DEFAULT_ROOT/${LABEL}_${STAMP}"
fi
WORKSPACE="$(resolve_workspace "$WORKSPACE")"
mkdir -p "$WORKSPACE"
export CAD_WORKSPACE_DIR="$WORKSPACE"

cleanup() {
  if [ "$KEEP_WORKSPACE" -eq 0 ] && [ -d "$WORKSPACE" ]; then
    rm -rf "$WORKSPACE"
  fi
}
trap cleanup EXIT

STATUS_OVERALL=0
DOCTOR_STATUS="skipped"
KICAD_STATUS="skipped"
KICAD_MCP_STATUS="skipped"
KICAD_MCP_REASON=""
FREECAD_STATUS="skipped"
PLATFORMIO_STATUS="skipped"

mkdir -p "$WORKSPACE/kicad-smoke" "$WORKSPACE/freecad-smoke" "$WORKSPACE/platformio-smoke/src"

log "workspace=$WORKSPACE"

if [ "$RUN_DOCTOR" -eq 1 ]; then
  if run "$CAD_STACK" doctor >"$WORKSPACE/doctor.log" 2>&1; then
    DOCTOR_STATUS="ok"
  else
    DOCTOR_STATUS="failed"
    STATUS_OVERALL=1
  fi
fi

if [ "$RUN_KICAD" -eq 1 ]; then
  if run "$CAD_STACK" kicad-cli version >"$WORKSPACE/kicad-smoke/kicad-cli.version.txt" 2>&1; then
    KICAD_STATUS="ok"
  else
    KICAD_STATUS="failed"
    STATUS_OVERALL=1
  fi
fi

if [ "$RUN_KICAD" -eq 1 ] && [ "$RUN_KICAD_MCP" -eq 1 ]; then
  if ! kicad_mcp_available; then
    KICAD_MCP_STATUS="unavailable"
    KICAD_MCP_REASON="missing finetune/kicad_mcp_server/package.json"
  elif run_kicad_mcp_smoke; then
    KICAD_MCP_STATUS="ok"
  else
    KICAD_MCP_STATUS="failed"
    KICAD_MCP_REASON="stdio initialize/tools-list handshake failed"
    STATUS_OVERALL=1
  fi
fi

if [ "$RUN_FREECAD" -eq 1 ]; then
  cat >"$WORKSPACE/freecad-smoke/cube.py" <<'EOF'
import FreeCAD
import Part

doc = FreeCAD.newDocument("CadSmoke")
obj = doc.addObject("Part::Feature", "Cube")
obj.Shape = Part.makeBox(10, 10, 10)
doc.recompute()
Part.export([obj], "/workspace/freecad-smoke/cube.step")
doc.saveAs("/workspace/freecad-smoke/cube.FCStd")
print("freecad-smoke:ok")
EOF
  if run "$CAD_STACK" freecad-cmd /workspace/freecad-smoke/cube.py >"$WORKSPACE/freecad-smoke/freecad.log" 2>&1; then
    FREECAD_STATUS="ok"
  else
    FREECAD_STATUS="failed"
    STATUS_OVERALL=1
  fi
fi

if [ "$RUN_PLATFORMIO" -eq 1 ]; then
  cat >"$WORKSPACE/platformio-smoke/platformio.ini" <<'EOF'
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
EOF
  cat >"$WORKSPACE/platformio-smoke/src/main.cpp" <<'EOF'
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
}

void loop() {
  delay(1000);
}
EOF
  if run "$CAD_STACK" pio run -d /workspace/platformio-smoke >"$WORKSPACE/platformio-smoke/pio.log" 2>&1; then
    PLATFORMIO_STATUS="ok"
  else
    PLATFORMIO_STATUS="failed"
    STATUS_OVERALL=1
  fi
fi

cat >"$WORKSPACE/summary.json" <<EOF
{
  "generated_at": "$(date +%Y-%m-%dT%H:%M:%S)",
  "workspace": "$WORKSPACE",
  "doctor": "$DOCTOR_STATUS",
  "kicad": "$KICAD_STATUS",
  "kicad_mcp": "$KICAD_MCP_STATUS",
  "kicad_mcp_reason": "$KICAD_MCP_REASON",
  "freecad": "$FREECAD_STATUS",
  "platformio": "$PLATFORMIO_STATUS",
  "tmpfs_backed": true,
  "notes": [
    "workspace rooted under tmpfs when using the default /dev/shm path",
    "kicad MCP smoke covers initialize plus tools/list on stdio when the local server sources are present",
    "OpenSCAD runtime is not containerized in deploy/cad/docker-compose.yml yet"
  ]
}
EOF

log "doctor=$DOCTOR_STATUS kicad=$KICAD_STATUS kicad_mcp=$KICAD_MCP_STATUS freecad=$FREECAD_STATUS platformio=$PLATFORMIO_STATUS"
log "summary=$WORKSPACE/summary.json"

exit "$STATUS_OVERALL"
