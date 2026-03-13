#!/usr/bin/env bash
# scripts/modules/promtail.sh — Module Promtail

module_promtail_config() {
  PROMTAIL_PORT=$(input_value "Promtail port" "${PROMTAIL_PORT:-9080}")
}

module_promtail_compose() {
  echo "  promtail:"
  echo "    profiles:"
  echo "      - observability"
  echo "    image: \${PROMTAIL_IMAGE:-grafana/promtail:3.5.3}"
  echo "    container_name: mascarade-promtail"
  echo "    restart: unless-stopped"
  echo "    entrypoint: [\"/bin/sh\", \"/usr/local/bin/promtail-entrypoint.sh\"]"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${PROMTAIL_PORT}:9080\""
  echo "    volumes:"
  echo "      - ./deploy/promtail/promtail-config.yaml:/etc/promtail/config.yml:ro"
  echo "      - ./deploy/promtail/entrypoint.sh:/usr/local/bin/promtail-entrypoint.sh:ro"
  echo "      - promtail-data:/var/lib/promtail"
  echo "      - /var/run/docker.sock:/var/run/docker.sock"
  echo "      - /var/log/journal:/var/log/journal:ro"
  echo "      - /run/log/journal:/run/log/journal:ro"
  echo "      - /etc/machine-id:/etc/machine-id:ro"
  echo "    depends_on:"
  echo "      loki:"
  echo "        condition: service_started"
  echo "    healthcheck:"
  echo "      test: [\"CMD\", \"promtail\", \"--version\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_promtail_volumes() {
  echo "  promtail-data:"
}
