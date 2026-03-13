#!/usr/bin/env bash
# scripts/modules/otel-collector.sh — Module OpenTelemetry Collector

module_otel_collector_config() {
  OTEL_COLLECTOR_GRPC_PORT=$(input_value "OTel Collector gRPC port" "${OTEL_COLLECTOR_GRPC_PORT:-4317}")
  OTEL_COLLECTOR_HTTP_PORT=$(input_value "OTel Collector HTTP port" "${OTEL_COLLECTOR_HTTP_PORT:-4318}")
  OTEL_COLLECTOR_HEALTH_PORT=$(input_value "OTel Collector health port" "${OTEL_COLLECTOR_HEALTH_PORT:-13133}")
}

module_otel_collector_compose() {
  echo "  otel-collector:"
  echo "    profiles:"
  echo "      - observability"
  echo "    image: \${OTEL_COLLECTOR_IMAGE:-otel/opentelemetry-collector-contrib:0.116.1}"
  echo "    container_name: mascarade-otel-collector"
  echo "    restart: unless-stopped"
  echo "    user: \"0:0\""
  echo "    command: [\"--config=/etc/otelcol-contrib/config.yaml\"]"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OTEL_COLLECTOR_GRPC_PORT}:4317\""
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OTEL_COLLECTOR_HTTP_PORT}:4318\""
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OTEL_COLLECTOR_HEALTH_PORT}:13133\""
  echo "    volumes:"
  echo "      - ./deploy/otel-collector/config.yaml:/etc/otelcol-contrib/config.yaml:ro"
  echo "    depends_on:"
  echo "      tempo:"
  echo "        condition: service_healthy"
  echo "    healthcheck:"
  echo "      test: [\"CMD\", \"/otelcol-contrib\", \"--version\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "    networks:"
  echo "      - mascarade-network"
}
