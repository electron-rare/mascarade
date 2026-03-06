#!/usr/bin/env bash
# scripts/modules/core.sh — Module Mascarade Core

module_core_config() {
  CORE_PORT=$(input_value "Port Core" "${CORE_PORT:-8100}")
  CORE_HOST=$(input_value "Host Core" "${CORE_HOST:-0.0.0.0}")
  DEFAULT_PROVIDER=$(input_value "Provider LLM par defaut" "${DEFAULT_PROVIDER:-claude}")
  DEFAULT_MODEL=$(input_value "Modele LLM par defaut" "${DEFAULT_MODEL:-claude-sonnet-4-6}")
}

module_core_compose() {
  echo "  core:"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.core"
  echo "    container_name: mascarade-core"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${CORE_PORT}:8100\""
  echo "    env_file:"
  echo "      - .env"
  echo "    environment:"
  echo "      CORE_HOST: \${CORE_HOST}"
  echo "      CORE_PORT: \${CORE_PORT}"
  echo "      DEFAULT_PROVIDER: \${DEFAULT_PROVIDER}"
  echo "      DEFAULT_MODEL: \${DEFAULT_MODEL}"
  echo "    volumes:"
  echo "      - core-data:/app/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_core_volumes() {
  echo "  core-data:"
}
