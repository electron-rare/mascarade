#!/usr/bin/env bash
# scripts/modules/litellm.sh — Module LiteLLM

module_litellm_config() {
  LITELLM_PORT=$(input_value "Port LiteLLM" "${LITELLM_PORT:-4000}")
}

module_litellm_compose() {
  echo "  litellm:"
  echo "    image: \${LITELLM_IMAGE:-ghcr.io/berriai/litellm@sha256:59a2736ac84800821fa0e1656487366089f2d29d10f8ae05c918df9c6e4940af}"
  echo "    container_name: mascarade-litellm"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${LITELLM_PORT}:4000\""
  echo "    env_file:"
  echo "      - .env"
  echo "    environment:"
  echo "      LITELLM_PORT: \${LITELLM_PORT}"
  if svc_selected "redis"; then
    echo "      REDIS_HOST: redis"
    echo "      REDIS_PORT: 6379"
  fi
  echo "    volumes:"
  echo "      - ./tools/litellm-config.yaml:/app/config.yaml:ro"
  echo "    command: [\"--config\", \"/app/config.yaml\"]"
  if svc_selected "redis"; then
    echo "    depends_on:"
    echo "      redis:"
    echo "        condition: service_healthy"
  fi
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"python -c 'import urllib.request; urllib.request.urlopen(\\\"http://127.0.0.1:4000/health/liveliness\\\", timeout=3)' >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 20s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_litellm_volumes() {
  :
}
