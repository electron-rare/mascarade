#!/usr/bin/env bash
# scripts/modules/ops-console.sh — Module Ops Console local

module_ops_console_config() {
  OPS_CONSOLE_PORT=$(input_value "Port Ops Console" "${OPS_CONSOLE_PORT:-80}")
}

module_ops_console_compose() {
  echo "  ops-console:"
  echo "    image: nginx:alpine"
  echo "    container_name: mascarade-ops-console"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${OPS_CONSOLE_PORT}:80\""
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
