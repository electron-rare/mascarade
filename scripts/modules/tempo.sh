#!/usr/bin/env bash
# scripts/modules/tempo.sh — Module Grafana Tempo

module_tempo_config() {
  TEMPO_PORT=$(input_value "Tempo port" "${TEMPO_PORT:-3201}")
}

module_tempo_compose() {
  echo "  tempo:"
  echo "    image: \${TEMPO_IMAGE:-grafana/tempo:latest}"
  echo "    container_name: mascarade-tempo"
  echo "    restart: unless-stopped"
  echo "    command: [\"-config.file=/etc/tempo/tempo.yaml\"]"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${TEMPO_PORT}:3200\""
  echo "    volumes:"
  echo "      - ./deploy/tempo/tempo.yaml:/etc/tempo/tempo.yaml:ro"
  echo "      - tempo-data:/var/tempo"
  echo "    healthcheck:"
  echo "      test: [\"CMD\", \"/tempo\", \"-version\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 12"
  echo "      start_period: 20s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_tempo_volumes() {
  echo "  tempo-data:"
}
