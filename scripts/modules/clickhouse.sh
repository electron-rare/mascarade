#!/usr/bin/env bash
# scripts/modules/clickhouse.sh — Module ClickHouse

module_clickhouse_config() {
  :
}

module_clickhouse_compose() {
  echo "  clickhouse:"
  echo "    image: \${CLICKHOUSE_IMAGE:-clickhouse/clickhouse-server@sha256:0b2d7824347397b2ba6fcb216f0ae772568105f1f47e19f0d3247e24c79bc10a}"
  echo "    container_name: mascarade-clickhouse"
  echo "    restart: unless-stopped"
  echo "    volumes:"
  echo "      - clickhouse-data:/var/lib/clickhouse"
  echo "      - ./deploy/clickhouse-config/langfuse-user.xml:/etc/clickhouse-server/users.d/langfuse-user.xml:ro"
  if [[ -f "$REPO_DIR/deploy/clickhouse-config/thread-pools.xml" ]]; then
    echo "      - ./deploy/clickhouse-config/thread-pools.xml:/etc/clickhouse-server/config.d/thread-pools.xml:ro"
  fi
  echo "    environment:"
  echo "      CLICKHOUSE_PASSWORD: \${CLICKHOUSE_PASSWORD:-}"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"clickhouse-client --query 'SELECT 1' >/dev/null 2>&1\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 15"
  echo "      start_period: 30s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_clickhouse_volumes() {
  echo "  clickhouse-data:"
}
