#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/control_plane_cli.sh
source "$SCRIPT_DIR/lib/control_plane_cli.sh"

ROOT="$(cp_project_root)"
API_DIR="$ROOT/api"
DEPLOY_DIR="$ROOT/deploy/control-plane"
VERBOSE="${VERBOSE:-0}"
YES="${YES:-0}"
ALLOW_EXAMPLE_ENV="${ALLOW_EXAMPLE_ENV:-0}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
SLEEP_INTERVAL="${SLEEP_INTERVAL:-2}"

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_control_plane.sh [options] <photon|kxkm|tower>

Targets:
  photon  Deploy the control plane and health endpoint
  kxkm    Deploy the GPU node agent and worker
  tower   Deploy the CPU node agent and worker

Options:
  --yes              Skip confirmation prompts
  --allow-example-env
                    Allow deploying env files that still contain placeholder values
  --verbose          Log commands
  --health-timeout N Health check timeout in seconds (default: 60)
  --help             Show this help
EOF
}

parse_args() {
  TARGET=""
  while (($# > 0)); do
    case "$1" in
      --yes)
        YES=1
        shift
        ;;
      --allow-example-env)
        ALLOW_EXAMPLE_ENV=1
        shift
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --health-timeout)
        HEALTH_TIMEOUT="${2:?missing value for --health-timeout}"
        shift 2
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
        TARGET="$1"
        shift
        break
        ;;
    esac
  done
}

target_config() {
  case "$1" in
    photon)
      TARGET_HOST="root@192.168.0.119"
      TARGET_REMOTE_PREFIX=""
      TARGET_RSYNC_PATH="rsync"
      TARGET_ENV_FILE="$DEPLOY_DIR/env/photon-machine.env.example"
      TARGET_SERVICE_FILES=("mascarade-control-plane.service")
      TARGET_ENV_DESTS=("/etc/mascarade/control-plane.env")
      TARGET_HEALTH_URL="http://127.0.0.1:${TARGET_PORT:-3000}/health"
      TARGET_CHECK_CMD="curl -fsS ${TARGET_HEALTH_URL}"
      ;;
    kxkm)
      TARGET_HOST="kxkm@kxkm-ai"
      TARGET_REMOTE_PREFIX="sudo -n"
      TARGET_RSYNC_PATH="sudo -n rsync"
      TARGET_ENV_FILE="$DEPLOY_DIR/env/kxkm-agent.env.example"
      TARGET_WORKER_ENV_FILE="$DEPLOY_DIR/env/kxkm-worker.env.example"
      TARGET_SERVICE_FILES=("mascarade-node-agent.service" "mascarade-node-worker.service")
      TARGET_ENV_DESTS=("/etc/mascarade/node-agent.env" "/etc/mascarade/node-worker.env")
      TARGET_CHECK_CMD="sudo -n systemctl is-active --quiet mascarade-node-agent.service && sudo -n systemctl is-active --quiet mascarade-node-worker.service"
      ;;
    tower)
      TARGET_HOST="clems@192.168.0.120"
      TARGET_REMOTE_PREFIX="sudo -n"
      TARGET_RSYNC_PATH="sudo -n rsync"
      TARGET_ENV_FILE="$DEPLOY_DIR/env/tower-agent.env.example"
      TARGET_WORKER_ENV_FILE="$DEPLOY_DIR/env/tower-worker.env.example"
      TARGET_SERVICE_FILES=("mascarade-node-agent.service" "mascarade-node-worker.service")
      TARGET_ENV_DESTS=("/etc/mascarade/node-agent.env" "/etc/mascarade/node-worker.env")
      TARGET_CHECK_CMD="sudo -n systemctl is-active --quiet mascarade-node-agent.service && sudo -n systemctl is-active --quiet mascarade-node-worker.service"
      ;;
    *)
      cp_die "Unknown target: $1"
      ;;
  esac
}

remote_exec() {
  local command="$1"
  cp_log INFO "ssh ${TARGET_HOST} ${command}"
  ssh "$TARGET_HOST" "set -euo pipefail; ${command}"
}

env_value() {
  local file="$1"
  local key="$2"
  awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "$file"
}

validate_env_file() {
  local file="$1"
  [[ -f "$file" ]] || cp_die "Missing env file: $file"

  if [[ "${ALLOW_EXAMPLE_ENV:-0}" == "1" ]]; then
    return 0
  fi

  if grep -Eq '(^|=)(change-me|replace-me|example-secret)([[:space:]]*$|$)' "$file"; then
    cp_die "Refusing to deploy placeholder env file: $file (use --allow-example-env to override)"
  fi
}

remote_install_file() {
  local source_file="$1"
  local destination="$2"
  local stage_dir
  stage_dir="$(remote_exec 'mktemp -d /tmp/mascarade-deploy.XXXXXX')"
  scp "$source_file" "${TARGET_HOST}:${stage_dir}/$(basename "$source_file")" >/dev/null
  remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }install -m 0644 ${stage_dir}/$(basename "$source_file") ${destination}"
  remote_exec "rm -rf ${stage_dir}"
}

remote_restart_control_plane() {
  if [[ "$1" == "photon" ]]; then
    remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }systemctl daemon-reload"
    remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }systemctl enable --now mascarade-control-plane.service"
  else
    remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }systemctl daemon-reload"
    remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }systemctl enable --now mascarade-node-agent.service mascarade-node-worker.service"
  fi
}

health_check_photon() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  local port
  port="$(awk -F= '/^PORT=/{print $2; exit}' "$TARGET_ENV_FILE" 2>/dev/null || true)"
  port="${port:-3000}"

  while (( SECONDS < deadline )); do
    if remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }curl -fsS http://127.0.0.1:${port}/health" >/dev/null; then
      cp_log INFO "health_check_ok photon"
      return 0
    fi
    sleep "$SLEEP_INTERVAL"
  done

  cp_die "Health check failed for photon after ${HEALTH_TIMEOUT}s"
}

health_check_nodes() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  local runtime_status_url=""
  runtime_status_url="$(env_value "$TARGET_ENV_FILE" "RUNTIME_STATUS_URL" 2>/dev/null || true)"
  while (( SECONDS < deadline )); do
    if remote_exec "$TARGET_CHECK_CMD" >/dev/null; then
      if [[ -n "$runtime_status_url" ]]; then
        if remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }curl -fsS ${runtime_status_url}" >/dev/null; then
          cp_log INFO "runtime_status_ok ${TARGET_HOST}"
          return 0
        fi
      else
        cp_log INFO "service_health_ok ${TARGET_HOST}"
        return 0
      fi
      cp_log INFO "health_check_ok ${TARGET_HOST}"
    fi
    sleep "$SLEEP_INTERVAL"
  done

  cp_die "Service health check failed for ${TARGET_HOST} after ${HEALTH_TIMEOUT}s"
}

deploy_photon() {
  cp_require_tools ssh rsync scp curl awk
  validate_env_file "$TARGET_ENV_FILE"
  remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }mkdir -p /opt/mascarade/api /etc/mascarade /var/lib/mascarade /var/log/mascarade"
  rsync -az --delete --exclude node_modules --exclude '.DS_Store' --rsync-path="$TARGET_RSYNC_PATH" "$API_DIR/" "${TARGET_HOST}:/opt/mascarade/api/"
  remote_install_file "$TARGET_ENV_FILE" "/etc/mascarade/control-plane.env"
  remote_install_file "$DEPLOY_DIR/systemd/mascarade-control-plane.service" "/etc/systemd/system/mascarade-control-plane.service"
  remote_restart_control_plane photon
  health_check_photon
}

deploy_node() {
  cp_require_tools ssh rsync scp
  validate_env_file "$TARGET_ENV_FILE"
  validate_env_file "$TARGET_WORKER_ENV_FILE"
  remote_exec "${TARGET_REMOTE_PREFIX:+${TARGET_REMOTE_PREFIX} }mkdir -p /opt/mascarade/api /etc/mascarade /var/lib/mascarade /var/log/mascarade"
  rsync -az --delete --exclude node_modules --exclude '.DS_Store' --rsync-path="$TARGET_RSYNC_PATH" "$API_DIR/" "${TARGET_HOST}:/opt/mascarade/api/"
  remote_install_file "$TARGET_ENV_FILE" "${TARGET_ENV_DESTS[0]}"
  remote_install_file "$TARGET_WORKER_ENV_FILE" "${TARGET_ENV_DESTS[1]}"
  remote_install_file "$DEPLOY_DIR/systemd/${TARGET_SERVICE_FILES[0]}" "/etc/systemd/system/${TARGET_SERVICE_FILES[0]}"
  remote_install_file "$DEPLOY_DIR/systemd/${TARGET_SERVICE_FILES[1]}" "/etc/systemd/system/${TARGET_SERVICE_FILES[1]}"
  remote_restart_control_plane "$TARGET"
  health_check_nodes
}

main() {
  parse_args "$@"
  if [[ -z "${TARGET:-}" ]]; then
    usage
    exit 2
  fi

  case "$TARGET" in
    photon|kxkm|tower) ;;
    *)
      usage
      exit 2
      ;;
  esac

  target_config "$TARGET"

  if [[ "$YES" != "1" ]]; then
    cp_confirm "Deploy control-plane assets to ${TARGET_HOST}?" || exit 1
  fi

  cp_require_tools ssh rsync scp curl
  remote_exec "command -v systemctl >/dev/null"
  remote_exec "command -v node >/dev/null"
  if [[ "$TARGET" == "photon" ]]; then
    deploy_photon
  else
    deploy_node
  fi

  printf 'Deployment finished for %s\n' "$TARGET"
}

main "$@"
