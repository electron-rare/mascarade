#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/control_plane_cli.sh
source "$SCRIPT_DIR/lib/control_plane_cli.sh"

CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://127.0.0.1:3000}"
CONTROL_PLANE_SHARED_TOKEN="${CONTROL_PLANE_SHARED_TOKEN:-}"
VERBOSE="${VERBOSE:-0}"
YES="${YES:-0}"
LIMIT="${LIMIT:-10}"
INTERVAL="${INTERVAL:-5}"
RAW="${RAW:-0}"

usage() {
  cat <<'EOF'
Usage:
  scripts/monitor.sh [options] <command>

Commands:
  dashboard   Show an overview with nodes, backpressure, providers, and events
  nodes       Show node state
  metrics     Print Prometheus metrics from the control plane
  events      Show recent control-plane events
  providers   Show LLM provider lanes
  state       Print the full cluster state as JSON
  watch       Refresh the dashboard in a loop
  menu        Interactive menu

Options:
  --url URL       Control-plane base URL
  --token TOKEN   Shared auth token
  --limit N      Event limit (default: 10)
  --interval S   Watch interval in seconds (default: 5)
  --raw          Print raw JSON where supported
  --verbose      Log requests
  --yes          Non-interactive defaults when possible
  --help         Show this help
EOF
}

parse_args() {
  COMMAND=""
  while (($# > 0)); do
    case "$1" in
      --url)
        CONTROL_PLANE_URL="${2:?missing value for --url}"
        shift 2
        ;;
      --token)
        CONTROL_PLANE_SHARED_TOKEN="${2:?missing value for --token}"
        shift 2
        ;;
      --limit)
        LIMIT="${2:?missing value for --limit}"
        shift 2
        ;;
      --interval)
        INTERVAL="${2:?missing value for --interval}"
        shift 2
        ;;
      --raw)
        RAW=1
        shift
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --yes)
        YES=1
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      --)
        shift
        break
        ;;
      -*)
        cp_die "Unknown option: $1"
        ;;
      *)
        COMMAND="$1"
        shift
        break
        ;;
    esac
  done
}

render_state() {
  local state_json="$1"
  python3 - "$state_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
nodes = data.get("nodes", [])
scheduler = data.get("scheduler", {})
backpressure = data.get("backpressure", {})
capacity = data.get("capacity", {})

print(f"Cluster: {capacity.get('cluster', 'mascarade-cluster')}")
print(f"Global queue bytes: {scheduler.get('global_queue_bytes', 0)}")
print(f"Leases: {len(scheduler.get('leases', []))}")
print(f"Pressure: {backpressure.get('load_factor', 0):.2f}")
print()
header = f"{'node_id':<14} {'role':<14} {'state':<10} {'queue':>5} {'CPU%':>6} {'GPU%':>6} {'RAM free':>12} {'VRAM free':>12} {'runtime':<10}"
print("Nodes")
print(header)
print("-" * len(header))
for node in nodes:
    print(
        f"{node.get('node_id', '-'):14.14} "
        f"{node.get('role', '-'):14.14} "
        f"{node.get('state', '-'):10.10} "
        f"{int(node.get('queue_depth', 0)):5d} "
        f"{float(node.get('cpu_util') or 0):6.1f} "
        f"{float(node.get('gpu_util') or 0):6.1f} "
        f"{int(node.get('ram_free_mb') or 0):12d} "
        f"{int(node.get('vram_free_mb') or 0):12d} "
        f"{(node.get('runtime_status') or '-'):10.10}"
    )
print()
print("Backpressure")
print(f"  items: {backpressure.get('global_queue_items', 0)}")
print(f"  bytes: {backpressure.get('global_queue_bytes', 0)}")
print(f"  under_pressure: {backpressure.get('is_under_pressure', False)}")
PY
}

render_nodes() {
  local state_json="$1"
  python3 - "$state_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
nodes = data.get("nodes", [])
header = f"{'node_id':<14} {'role':<14} {'state':<10} {'queue':>5} {'CPU%':>6} {'GPU%':>6} {'RAM free':>12} {'VRAM free':>12} {'failure':>8}"
print(header)
print("-" * len(header))
for node in nodes:
    print(
        f"{node.get('node_id', '-'):14.14} "
        f"{node.get('role', '-'):14.14} "
        f"{node.get('state', '-'):10.10} "
        f"{int(node.get('queue_depth', 0)):5d} "
        f"{float(node.get('cpu_util') or 0):6.1f} "
        f"{float(node.get('gpu_util') or 0):6.1f} "
        f"{int(node.get('ram_free_mb') or 0):12d} "
        f"{int(node.get('vram_free_mb') or 0):12d} "
        f"{float(node.get('recent_failure_rate') or 0):8.2f}"
    )
PY
}

render_events() {
  local events_json="$1"
  if [[ "$RAW" == "1" ]]; then
    printf '%s\n' "$events_json" | cp_json_pretty
    return
  fi

  python3 - "$events_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
events = data.get("events", [])
if not events:
    print("No recent events.")
    raise SystemExit(0)

header = f"{'ts':<24} {'level':<6} {'event_type':<28} {'project':<14} {'node':<12} {'request':<16} {'lease':<16}"
print(header)
print("-" * len(header))
for event in events:
    payload = event.get("data", {})
    print(
        f"{event.get('ts', '-'):24.24} "
        f"{event.get('level', '-'):6.6} "
        f"{event.get('event_type', '-'):28.28} "
        f"{(payload.get('project_id') or '-'):14.14} "
        f"{(payload.get('node_id') or '-'):12.12} "
        f"{(payload.get('request_id') or '-'):16.16} "
        f"{(payload.get('lease_id') or '-'):16.16}"
    )
PY
}

render_providers() {
  local providers_json="$1"
  python3 - "$providers_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
providers = data.get("data", {}).get("providers", [])
header = f"{'lane':<10} {'provider':<14} {'model':<24} {'status':<12}"
print(header)
print("-" * len(header))
for provider in providers:
    print(
        f"{provider.get('lane', '-'):10.10} "
        f"{provider.get('provider', '-'):14.14} "
        f"{provider.get('model', '-'):24.24} "
        f"{provider.get('status', '-'):12.12}"
    )
PY
}

cmd_state() {
  local state_json
  state_json="$(cp_http GET "/api/cluster/state")"
  if [[ "$RAW" == "1" ]]; then
    printf '%s\n' "$state_json" | cp_json_pretty
  else
    render_state "$state_json"
  fi
}

cmd_nodes() {
  local state_json
  state_json="$(cp_http GET "/api/cluster/state")"
  render_nodes "$state_json"
}

cmd_metrics() {
  cp_http GET "/metrics"
}

cmd_events() {
  local events_json
  events_json="$(cp_http GET "/api/cluster/events?limit=${LIMIT}")"
  render_events "$events_json"
}

cmd_providers() {
  local providers_json
  providers_json="$(cp_http GET "/api/v2/llm-providers")"
  if [[ "$RAW" == "1" ]]; then
    printf '%s\n' "$providers_json" | cp_json_pretty
  else
    render_providers "$providers_json"
  fi
}

cmd_dashboard() {
  local state_json events_json providers_json metrics_text
  state_json="$(cp_http GET "/api/cluster/state")"
  events_json="$(cp_http GET "/api/cluster/events?limit=${LIMIT}")"
  providers_json="$(cp_http GET "/api/v2/llm-providers")"
  metrics_text="$(cp_http GET "/metrics")"

  clear
  printf 'Mascarade Control Plane Dashboard\n'
  printf 'URL: %s\n\n' "$CONTROL_PLANE_URL"
  render_state "$state_json"
  printf '\nProviders\n'
  render_providers "$providers_json"
  printf '\nMetrics preview\n'
  printf '%s\n' "$metrics_text" | head -n 12
  printf '\nRecent events\n'
  render_events "$events_json"
}

cmd_watch() {
  trap 'printf "\n"; exit 0' INT TERM
  while true; do
    cmd_dashboard
    sleep "$INTERVAL"
  done
}

menu_loop() {
  while true; do
    local choice
    choice="$(cp_choose "Mascarade monitoring" dashboard nodes metrics events providers state watch quit)"
    case "$choice" in
      dashboard) cmd_dashboard ;;
      nodes) cmd_nodes ;;
      metrics) cmd_metrics ;;
      events) cmd_events ;;
      providers) cmd_providers ;;
      state) cmd_state ;;
      watch) cmd_watch ;;
      quit) return 0 ;;
    esac

    if cp_is_tty; then
      read -r -p "Press Enter to continue..." _
    fi
  done
}

main() {
  cp_require_tools curl python3 head
  parse_args "$@"

  if [[ -z "${COMMAND:-}" ]]; then
    if [[ "$YES" == "1" || ! cp_is_tty ]]; then
      COMMAND="dashboard"
    else
      COMMAND="menu"
    fi
  fi

  case "$COMMAND" in
    dashboard) cmd_dashboard ;;
    nodes) cmd_nodes ;;
    metrics) cmd_metrics ;;
    events) cmd_events ;;
    providers) cmd_providers ;;
    state) cmd_state ;;
    watch) cmd_watch ;;
    menu) menu_loop ;;
    *)
      usage
      exit 2
      ;;
  esac
}

main "$@"
