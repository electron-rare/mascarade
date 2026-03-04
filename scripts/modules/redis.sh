#!/usr/bin/env bash
# scripts/modules/redis.sh — Module Redis

module_redis_config() {
  input_value "REDIS_PORT" "Redis port" "6379"
}

module_redis_compose() {
  echo "  redis:"
  echo "    image: redis:7-alpine"
  echo "    container_name: mascarade-redis"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${REDIS_PORT}:6379\""
  echo "    volumes:"
  echo "      - redis-data:/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_redis_volumes() {
  echo "  redis-data:"
}
