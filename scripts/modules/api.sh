#!/usr/bin/env bash
# scripts/modules/api.sh — Module Mascarade API

module_api_config() {
  API_PORT=$(input_value "Port API" "${API_PORT:-3100}")
  API_HOST=$(input_value "Host API" "${API_HOST:-0.0.0.0}")
  CORE_URL=$(input_value "URL Core interne" "${CORE_URL:-http://core:${CORE_PORT:-8100}}")
}

module_api_compose() {
  echo "  api:"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.api"
  echo "    container_name: mascarade-api"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${API_PORT}:3000\""
  echo "    env_file:"
  echo "      - .env"
  echo "    environment:"
  echo "      CORE_URL: \${CORE_URL}"
  echo "      API_PORT: 3000"
  if svc_selected "core"; then
    echo "    depends_on:"
    echo "      - core"
  fi
  echo "    networks:"
  echo "      - mascarade-network"
}

module_api_volumes() {
  :
}
