#!/usr/bin/env bash
# scripts/modules/blackbox-exporter.sh — Module Prometheus Blackbox Exporter

module_blackbox_exporter_config() {
  BLACKBOX_EXPORTER_PORT=$(input_value "Blackbox Exporter port" "${BLACKBOX_EXPORTER_PORT:-9115}")
}

module_blackbox_exporter_compose() {
  echo "  blackbox-exporter:"
  echo "    image: \${BLACKBOX_EXPORTER_IMAGE:-prom/blackbox-exporter:latest}"
  echo "    container_name: mascarade-blackbox-exporter"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${BLACKBOX_EXPORTER_PORT}:9115\""
  echo "    command: [\"--config.file=/etc/blackbox/blackbox.yml\"]"
  echo "    volumes:"
  echo "      - ./deploy/prometheus/blackbox.yml:/etc/blackbox/blackbox.yml:ro"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1:9115/-/healthy >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 10s"
  echo "    networks:"
  echo "      - mascarade-network"
}
