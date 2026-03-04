#!/usr/bin/env bash
set -euo pipefail

# Apply ops-console migration compatibility to observability checks.
# Supports both V3 (ops-console-v3) and legacy V2 (zacus-ops-console).

BASE_DIR="/opt/docker-studio-ai/tools/dev/docker-studio-ai"
CHECK_SCRIPT="${BASE_DIR}/scripts/container_observability_check.sh"
HEALTHCHECK_SCRIPT="${BASE_DIR}/scripts/healthcheck.sh"
ENV_LOCAL="${BASE_DIR}/.env.local"

require_file() {
  local f="$1"
  if [ ! -f "$f" ]; then
    echo "Missing file: $f" >&2
    exit 1
  fi
}

require_file "${CHECK_SCRIPT}"
require_file "${HEALTHCHECK_SCRIPT}"
require_file "${ENV_LOCAL}"

if ! grep -q 'ops-console' "${CHECK_SCRIPT}"; then
  sed -i 's/zacus-ops-console/ops-console/g' "${CHECK_SCRIPT}"
fi

if ! grep -q 'Migration-safe alias: accept either V3' "${CHECK_SCRIPT}"; then
  perl -0pi -e 's/status="\$\(docker ps -a --filter "name=\^\/\$\{name\}\$" --format '"'"'\{\{\.Status\}\}'"'"' \| head -n1 \|\| true\)"/if [ "\$name" = "ops-console" ]; then\n    status="\$(docker ps -a --filter "name=^\/ops-console-v3\$" --format '"'"'\{\{\.Status\}\}'"'"' \| head -n1 \|\| true)"\n    if [ -z "\$status" ]; then\n      status="\$(docker ps -a --filter "name=^\/zacus-ops-console\$" --format '"'"'\{\{\.Status\}\}'"'"' \| head -n1 \|\| true)"\n    fi\n  else\n    status="\$(docker ps -a --filter "name=^\/\$\{name\}\$" --format '"'"'\{\{\.Status\}\}'"'"' \| head -n1 \|\| true)"\n  fi/s' "${CHECK_SCRIPT}"
fi

if grep -q 'check_container_running "zacus-ops-console"' "${HEALTHCHECK_SCRIPT}"; then
  perl -0pi -e 's/check_container_running "zacus-ops-console"/if container_exists "ops-console-v3"; then\n  check_container_running "ops-console-v3"\nelif container_exists "zacus-ops-console"; then\n  check_container_running "zacus-ops-console"\nelse\n  fail "Container ops-console" "missing (ops-console-v3 and zacus-ops-console not found)"\nfi/s' "${HEALTHCHECK_SCRIPT}"
fi

sed -i 's/,zacus-ops-console$/,\,ops-console/' "${ENV_LOCAL}"
sed -i 's/,zacus-ops-console,/,ops-console,/' "${ENV_LOCAL}"

systemctl daemon-reload
systemctl restart container-observability.timer
systemctl start container-observability.service || true

echo "Applied observability ops-console compatibility."
