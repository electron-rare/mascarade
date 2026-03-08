#!/bin/sh
set -eu

AUTH_DIR="/etc/nginx/auth"
AUTH_FILE="${AUTH_DIR}/ops-tools.htpasswd"
AUTH_USER="${EDGE_PROXY_OPS_AUTH_USER:-ops}"
AUTH_PASSWORD="${EDGE_PROXY_OPS_AUTH_PASSWORD:-}"

mkdir -p "${AUTH_DIR}"

if [ -z "${AUTH_PASSWORD}" ]; then
  AUTH_PASSWORD="$(openssl rand -hex 16)"
fi

printf '%s:%s\n' "${AUTH_USER}" "$(openssl passwd -apr1 "${AUTH_PASSWORD}")" > "${AUTH_FILE}"
chmod 600 "${AUTH_FILE}"
