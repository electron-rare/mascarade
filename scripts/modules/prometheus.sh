#!/usr/bin/env bash
# scripts/modules/prometheus.sh — Module Prometheus

module_prometheus_config() {
  input_value "PROMETHEUS_PORT" "Prometheus port" "9090"
}

module_prometheus_compose() {
  echo "  prometheus:"
  echo "    image: prom/prometheus:latest"
  echo "    container_name: mascarade-prometheus"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${PROMETHEUS_PORT}:9090\""
  echo "    volumes:"
  echo "      - prometheus-data:/prometheus"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_prometheus_volumes() {
  echo "  prometheus-data:"
}
