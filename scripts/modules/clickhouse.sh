#!/usr/bin/env bash
# scripts/modules/clickhouse.sh — Module ClickHouse

module_clickhouse_config() {
  :
}

module_clickhouse_compose() {
  echo "  clickhouse:"
  echo "    image: clickhouse/clickhouse-server:latest"
  echo "    container_name: mascarade-clickhouse"
  echo "    restart: unless-stopped"
  echo "    volumes:"
  echo "      - clickhouse-data:/var/lib/clickhouse"
  echo "      - ./deploy/clickhouse/users.d/langfuse-user.xml:/etc/clickhouse-server/users.d/langfuse-user.xml:ro"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_clickhouse_volumes() {
  echo "  clickhouse-data:"
}
