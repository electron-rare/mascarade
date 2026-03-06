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
  echo "      - \"127.0.0.1:\${LITELLM_PORT}:4000\""
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
  echo "    networks:"
  echo "      - mascarade-network"
}

module_litellm_volumes() {
  :
}
