#!/usr/bin/env bash
# scripts/modules/ops-console.sh — Module Ops Console local

module_ops_console_config() {
  OPS_CONSOLE_PORT=$(input_value "Port Ops Console" "${OPS_CONSOLE_PORT:-80}")
  OPS_CONSOLE_BIND_HOST=$(input_value "Host bind Ops Console" "${OPS_CONSOLE_BIND_HOST:-${PUBLISH_BIND_HOST:-0.0.0.0}}")
}

module_ops_console_compose() {
  echo "  ops-console:"
  echo "    image: nginx:alpine"
  echo "    container_name: mascarade-ops-console"
  echo "    restart: unless-stopped"
  if svc_selected "edge-proxy"; then
    echo "    expose:"
    echo "      - \"80\""
  else
    echo "    ports:"
    echo "      - \"\${OPS_CONSOLE_BIND_HOST:-\${PUBLISH_BIND_HOST:-0.0.0.0}}:\${OPS_CONSOLE_PORT}:80\""
  fi
  echo "    volumes:"
  echo "      - ./deploy/ops-console/index.html:/usr/share/nginx/html/index.html:ro"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1:80/ >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 5"
  echo "      start_period: 5s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_ops_console_volumes() {
  :
}
