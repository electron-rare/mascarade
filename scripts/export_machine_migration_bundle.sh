#!/usr/bin/env bash
set -euo pipefail

# Export a migration-oriented machine snapshot into the repo.
# Usage:
#   scripts/export_machine_migration_bundle.sh [output_dir]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${1:-${ROOT_DIR}/docs/migration/snapshots/${STAMP}}"

mkdir -p "${OUT_DIR}"

run_capture() {
  local file="$1"
  shift
  {
    echo "# command: $*"
    echo "# date: $(date -Is)"
    echo
    "$@"
  } > "${OUT_DIR}/${file}" 2>&1 || true
}

sanitize_env_file() {
  local src="$1"
  local dst="$2"
  [ -f "${src}" ] || return 0

  awk -F= '
    /^[[:space:]]*#/ { print; next }
    /^[[:space:]]*$/ { print; next }
    {
      key=$1
      val=$0
      sub(/^[^=]*=/, "", val)
      upper=key
      for (i=1; i<=length(upper); i++) {
        c=substr(upper, i, 1)
        if (c ~ /[a-z]/) {
          upper=substr(upper,1,i-1) toupper(c) substr(upper,i+1)
        }
      }
      if (upper ~ /(PASSWORD|PASS|TOKEN|SECRET|KEY|PRIVATE|CREDENTIAL)/) {
        print key "=***REDACTED***"
      } else {
        print $0
      }
    }
  ' "${src}" > "${dst}"
}

{
  echo "# Machine Migration Snapshot"
  echo
  echo "- Generated: $(date -Is)"
  echo "- Host: $(hostname)"
  echo "- Repo root: ${ROOT_DIR}"
  echo "- Output: ${OUT_DIR}"
} > "${OUT_DIR}/README.md"

run_capture host_overview.txt bash -lc '
  echo "== host ==";
  hostname;
  echo;
  echo "== os-release ==";
  cat /etc/os-release;
  echo;
  echo "== kernel ==";
  uname -a;
  echo;
  echo "== uptime/load ==";
  uptime;
  cat /proc/loadavg;
  echo;
  echo "== cpu ==";
  nproc;
  echo;
  echo "== memory ==";
  free -h;
  echo;
  echo "== disk ==";
  df -h;
'

run_capture network_ports.txt bash -lc '
  echo "== ip -4 ==";
  ip -4 -o addr show scope global;
  echo;
  echo "== listening ports ==";
  ss -tulpn;
'

run_capture systemd_services.txt bash -lc '
  echo "== failed units ==";
  systemctl --failed --no-pager;
  echo;
  echo "== critical services ==";
  for s in docker sshd systemd-resolved; do
    printf "%s: " "$s";
    systemctl is-active "$s" || true;
  done;
  echo;
  echo "== timers (top) ==";
  systemctl list-timers --all --no-pager | sed -n "1,60p";
'

run_capture journal_errors_last_hour.txt bash -lc '
  journalctl -p err --since "1 hour ago" --no-pager
'

run_capture docker_ps_a.txt docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
run_capture docker_stats.txt docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'
run_capture docker_system_df.txt docker system df
run_capture docker_volumes.txt docker volume ls
run_capture docker_networks.txt docker network ls

run_capture docker_restart_counts.txt bash -lc '
  for c in $(docker ps -a --format "{{.Names}}"); do
    rc=$(docker inspect --format="{{.RestartCount}}" "$c" 2>/dev/null || echo 0)
    status=$(docker inspect --format="{{.State.Status}}" "$c" 2>/dev/null || echo unknown)
    printf "%-35s restart=%-6s status=%s\n" "$c" "$rc" "$status"
  done | sort
'

run_capture docker_unhealthy.txt docker ps --filter 'health=unhealthy' --format '{{.Names}}: {{.Status}}'

run_capture top_processes_mem.txt bash -lc 'ps aux --sort=-%mem | sed -n "1,30p"'
run_capture top_processes_cpu.txt bash -lc 'ps aux --sort=-%cpu | sed -n "1,30p"'

run_capture skills_global_listing.txt bash -lc '
  ls -la /opt/skills-global/all;
  echo;
  echo "count:";
  find /opt/skills-global/all -mindepth 1 -maxdepth 1 -type d | wc -l;
  echo;
  echo "size:";
  du -sh /opt/skills-global/all;
'

run_capture skills_links.txt bash -lc '
  ls -la /root/.codex/skills 2>/dev/null || true;
  ls -la /root/.claude/skills 2>/dev/null || true;
  ls -la '"${ROOT_DIR}"'/.claude/skills 2>/dev/null || true;
'

sanitize_env_file "${ROOT_DIR}/.env" "${OUT_DIR}/mascarade.env.redacted"
sanitize_env_file "${ROOT_DIR}/.env.example" "${OUT_DIR}/mascarade.env.example.redacted"
sanitize_env_file "/opt/docker-studio-ai/tools/dev/docker-studio-ai/.env.local" "${OUT_DIR}/docker_studio_ai.env.local.redacted"

run_capture versions.txt bash -lc '
  echo "docker: $(docker --version 2>/dev/null || echo N/A)";
  echo "compose: $(docker compose version 2>/dev/null | head -n1 || echo N/A)";
  echo "python3: $(python3 --version 2>/dev/null || echo N/A)";
  echo "node: $(node --version 2>/dev/null || echo N/A)";
'

echo "${OUT_DIR}" > "${ROOT_DIR}/docs/migration/LATEST_SNAPSHOT_PATH.txt"
echo "Snapshot exported to: ${OUT_DIR}"
