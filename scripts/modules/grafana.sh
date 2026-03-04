#!/usr/bin/env bash
# scripts/modules/grafana.sh — Module Grafana

module_grafana_config() {
  input_value "GRAFANA_PORT" "Grafana port" "3001"
}

module_grafana_compose() {
  echo "  grafana:"
  echo "    image: grafana/grafana:latest"
  echo "    container_name: mascarade-grafana"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${GRAFANA_PORT}:3000\""
  echo "    volumes:"
  echo "      - grafana-data:/var/lib/grafana"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_grafana_volumes() {
  echo "  grafana-data:"
}
