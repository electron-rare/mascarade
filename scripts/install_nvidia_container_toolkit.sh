#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: scripts/install_nvidia_container_toolkit.sh [options]

Installe et configure nvidia-container-toolkit pour Docker sur l'hote.

Options:
  --check-only   Verifie l'etat actuel sans rien modifier
  --verify-run   Lance aussi un smoke test `docker run --gpus all ... nvidia-smi`
  --quiet        Reduit la sortie
  -h, --help     Affiche cette aide

Notes:
  - Le script doit etre execute avec sudo/root.
  - Il modifie /etc/apt/sources.list.d/, /usr/share/keyrings/ et /etc/docker/daemon.json.
  - Le restart Docker peut interrompre brievement les conteneurs en cours.
HELP
}

QUIET=false
CHECK_ONLY=false
VERIFY_RUN=false
ORIGINAL_ARGS=("$@")

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      CHECK_ONLY=true
      ;;
    --verify-run)
      VERIFY_RUN=true
      ;;
    --quiet)
      QUIET=true
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
  shift
done

log() {
  if [[ "$QUIET" != true ]]; then
    echo "$@"
  fi
}

fail() {
  echo "$@" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_linux() {
  [[ "$(uname -s)" == "Linux" ]] || fail "This script only supports Linux hosts"
}

require_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if [[ -t 0 ]]; then
    log "Re-running with sudo..."
    exec sudo --preserve-env=DEBIAN_FRONTEND "$0" "${ORIGINAL_ARGS[@]}"
  fi

  fail "Root is required. Re-run with sudo, for example: sudo $0 ${ORIGINAL_ARGS[*]}"
}

check_state() {
  local docker_runtimes
  log "Checking Docker/NVIDIA state..."

  if ! command -v docker >/dev/null 2>&1; then
    fail "docker is not installed"
  fi

  if ! docker info >/dev/null 2>&1; then
    fail "docker daemon is unreachable"
  fi

  docker_runtimes="$(docker info --format '{{json .Runtimes}} {{json .DefaultRuntime}}')"
  log "Docker runtimes: $docker_runtimes"

  if command -v nvidia-ctk >/dev/null 2>&1; then
    log "nvidia-ctk: $(nvidia-ctk --version | head -n 1)"
  else
    log "nvidia-ctk: not installed"
  fi
}

backup_daemon_json() {
  if [[ -f /etc/docker/daemon.json ]]; then
    local backup_path="/etc/docker/daemon.json.bak.$(date +%Y%m%d%H%M%S)"
    cp /etc/docker/daemon.json "$backup_path"
    log "Backed up /etc/docker/daemon.json to $backup_path"
  fi
}

install_repo() {
  local keyring="/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"
  local repo_file="/etc/apt/sources.list.d/nvidia-container-toolkit.list"
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  install -m 0755 -d /usr/share/keyrings /etc/apt/sources.list.d

  log "Refreshing apt metadata..."
  apt-get update

  log "Installing base dependencies..."
  DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg

  log "Installing NVIDIA repository key..."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor --yes -o "$tmp_dir/nvidia-container-toolkit-keyring.gpg"
  install -m 0644 "$tmp_dir/nvidia-container-toolkit-keyring.gpg" "$keyring"

  log "Installing NVIDIA apt repository..."
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed "s#deb https://#deb [signed-by=${keyring}] https://#g" > "$tmp_dir/nvidia-container-toolkit.list"
  install -m 0644 "$tmp_dir/nvidia-container-toolkit.list" "$repo_file"

  log "Installing nvidia-container-toolkit..."
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y nvidia-container-toolkit
}

restart_docker() {
  if command -v systemctl >/dev/null 2>&1; then
    log "Restarting Docker via systemctl..."
    systemctl restart docker
    return 0
  fi

  if command -v service >/dev/null 2>&1; then
    log "Restarting Docker via service..."
    service docker restart
    return 0
  fi

  fail "Could not restart Docker automatically (systemctl/service not found)"
}

configure_runtime() {
  need_cmd nvidia-ctk

  backup_daemon_json

  log "Configuring Docker runtime via nvidia-ctk..."
  nvidia-ctk runtime configure --runtime=docker

  restart_docker
}

verify_runtime() {
  local docker_runtimes

  need_cmd docker
  docker_runtimes="$(docker info --format '{{json .Runtimes}} {{json .DefaultRuntime}}')"
  log "Docker runtimes after configuration: $docker_runtimes"

  if ! grep -q '"nvidia"' <<<"$docker_runtimes"; then
    fail "Docker runtimes do not include nvidia after configuration"
  fi

  if [[ "$VERIFY_RUN" == true ]]; then
    log "Running GPU smoke test in Docker..."
    docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
  fi
}

main() {
  require_linux

  if [[ "$CHECK_ONLY" == true ]]; then
    check_state
    return 0
  fi

  require_root
  install_repo
  configure_runtime
  check_state
  verify_runtime
}

main "$@"
