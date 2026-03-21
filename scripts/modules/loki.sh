#!/usr/bin/env bash
# scripts/modules/loki.sh — Module Loki

module_loki_config() {
  LOKI_PORT=$(input_value "Loki port" "${LOKI_PORT:-3101}")
}

module_loki_compose() {
  echo "  loki:"
  echo "    profiles:"
  echo "      - observability"
  echo "    image: \${LOKI_IMAGE:-grafana/loki:3.5.3}"
  echo "    container_name: mascarade-loki"
  echo "    restart: unless-stopped"
  echo "    command: [\"-config.file=/etc/loki/local-config.yaml\"]"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${LOKI_PORT}:3100\""
  echo "    volumes:"
  echo "      - ./deploy/loki/loki-config.yaml:/etc/loki/local-config.yaml:ro"
  echo "      - loki-data:/loki"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"wget -qO- http://localhost:3100/ready >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_loki_volumes() {
  echo "  loki-data:"
}
