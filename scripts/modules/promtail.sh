#!/usr/bin/env bash
# scripts/modules/promtail.sh — Module Promtail

module_promtail_config() {
  PROMTAIL_PORT=$(input_value "Promtail port" "${PROMTAIL_PORT:-9080}")
}

module_promtail_compose() {
  echo "  promtail:"
  echo "    image: \${PROMTAIL_IMAGE:-grafana/promtail:3.5.3}"
  echo "    container_name: mascarade-promtail"
  echo "    restart: unless-stopped"
  echo "    command: [\"-config.file=/etc/promtail/config.yml\"]"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${PROMTAIL_PORT}:9080\""
  echo "    volumes:"
  echo "      - ./deploy/promtail/promtail-config.yaml:/etc/promtail/config.yml:ro"
  echo "      - /var/lib/docker/containers:/var/lib/docker/containers:ro"
  echo "      - /var/log/journal:/var/log/journal:ro"
  echo "      - /run/log/journal:/run/log/journal:ro"
  echo "      - /etc/machine-id:/etc/machine-id:ro"
  echo "    depends_on:"
  echo "      loki:"
  echo "        condition: service_started"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"wget -qO- http://localhost:9080/ready >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "    networks:"
  echo "      - mascarade-network"
}
