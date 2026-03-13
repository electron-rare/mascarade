#!/usr/bin/env bash
# scripts/modules/prometheus.sh — Module Prometheus

module_prometheus_config() {
  PROMETHEUS_PORT=$(input_value "Prometheus port" "${PROMETHEUS_PORT:-9090}")
}

module_prometheus_compose() {
  echo "  prometheus:"
  echo "    profiles:"
  echo "      - observability"
  echo "    image: \${PROMETHEUS_IMAGE:-prom/prometheus@sha256:4a61322ac1103a0e3aea2a61ef1718422a48fa046441f299d71e660a3bc71ae9}"
  echo "    container_name: mascarade-prometheus"
  echo "    restart: unless-stopped"
  echo "    command:"
  echo "      - --config.file=/etc/prometheus/prometheus.yml"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${PROMETHEUS_PORT}:9090\""
  echo "    volumes:"
  echo "      - ./deploy/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"
  echo "      - prometheus-data:/prometheus"
  echo "    depends_on:"
  echo "      blackbox-exporter:"
  echo "        condition: service_started"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"wget -qO- http://localhost:9090/-/healthy >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 5"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_prometheus_volumes() {
  echo "  prometheus-data:"
}
