#!/usr/bin/env bash
# scripts/modules/redis.sh — Module Redis

module_redis_config() {
  REDIS_PORT=$(input_value "Redis port" "${REDIS_PORT:-6379}")
}

module_redis_compose() {
  echo "  redis:"
  echo "    image: \${REDIS_IMAGE:-redis@sha256:8b81dd37ff027bec4e516d41acfbe9fe2460070dc6d4a4570a2ac5b9d59df065}"
  echo "    container_name: mascarade-redis"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${REDIS_PORT}:6379\""
  echo "    volumes:"
  echo "      - redis-data:/data"
  echo "    healthcheck:"
  echo "      test: [\"CMD\", \"redis-cli\", \"ping\"]"
  echo "      interval: 10s"
  echo "      timeout: 3s"
  echo "      retries: 10"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_redis_volumes() {
  echo "  redis-data:"
}
