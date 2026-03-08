#!/usr/bin/env bash
# scripts/modules/grafana.sh — Module Grafana

module_grafana_config() {
  GRAFANA_PORT=$(input_value "Grafana port" "${GRAFANA_PORT:-3001}")
}

module_grafana_compose() {
  echo "  grafana:"
  echo "    image: \${GRAFANA_IMAGE:-grafana/grafana@sha256:b0ae311af06228bcfd4a620504b653db80f5b91e94dc3dc2a5b7dab202bcde20}"
  echo "    container_name: mascarade-grafana"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${GRAFANA_PORT}:3000\""
  echo "    volumes:"
  echo "      - grafana-data:/var/lib/grafana"
  echo "      - ./deploy/grafana/provisioning:/etc/grafana/provisioning:ro"
  echo "    environment:"
  echo "      GF_SERVER_ROOT_URL: \${GRAFANA_PUBLIC_ORIGIN:-http://grafana.localhost}"
  echo "      GF_SERVER_DOMAIN: \${EDGE_PROXY_GRAFANA_SERVER_NAME:-grafana.localhost}"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"curl -fsS http://localhost:3000/api/health >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 5"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_grafana_volumes() {
  echo "  grafana-data:"
}
