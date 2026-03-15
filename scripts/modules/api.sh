#!/usr/bin/env bash
# scripts/modules/api.sh — Module Mascarade API

module_api_config() {
  API_PORT=$(input_value "Port API" "${API_PORT:-3100}")
  API_HOST=$(input_value "Host API" "${API_HOST:-0.0.0.0}")
  CORE_URL=$(input_value "URL Core interne" "${CORE_URL:-http://core:${CORE_PORT:-8100}}")
}

module_api_compose() {
  echo "  api:"
  echo "    profiles:"
  echo "      - core"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.api"
  echo "    container_name: mascarade-api"
  echo "    restart: unless-stopped"
  echo "    user: \"\${API_RUNTIME_UID:-1000}:\${API_RUNTIME_GID:-1000}\""
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${API_PORT}:3000\""
  echo "    env_file:"
  echo "      - .env"
  echo "    environment:"
  echo "      CORE_URL: \${CORE_URL}"
  echo "      API_PORT: 3000"
  echo "      HOME: /tmp"
  echo "      KILL_LIFE_ROOT: \${KILL_LIFE_ROOT:-/workspace/Kill_LIFE}"
  echo "    volumes:"
  echo "      - ../Kill_LIFE:\${KILL_LIFE_ROOT:-/workspace/Kill_LIFE}:rw"
  if svc_selected "core"; then
    echo "    depends_on:"
    echo "      - core"
  fi
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"node -e \\\"fetch('http://127.0.0.1:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\\\"\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 20s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_api_volumes() {
  :
}
