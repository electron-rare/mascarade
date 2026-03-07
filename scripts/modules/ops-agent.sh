#!/usr/bin/env bash
# scripts/modules/ops-agent.sh — Module Ops Agent

module_ops_agent_config() {
  OPS_AGENT_PORT=$(input_value "Ops Agent port" "${OPS_AGENT_PORT:-9200}")
}

module_ops_agent_compose() {
  echo "  ops-agent:"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.ops-agent"
  echo "    container_name: mascarade-ops-agent"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OPS_AGENT_PORT}:9200\""
  echo "    env_file:"
  echo "      - .env"
  echo "    environment:"
  echo "      OPS_AGENT_PORT: 9200"
  echo "      AGENTSIGHT_URL: \${AGENTSIGHT_URL:-}"
  echo "      LOKI_URL: \${LOKI_URL:-http://loki:3100}"
  echo "    volumes:"
  echo "      - /var/run/docker.sock:/var/run/docker.sock"
  echo "      - /var/log/journal:/var/log/journal:ro"
  echo "      - /run/log/journal:/run/log/journal:ro"
  echo "      - /etc/machine-id:/etc/machine-id:ro"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"python -c \\\"import urllib.request; urllib.request.urlopen('http://localhost:9200/health')\\\"\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "    networks:"
  echo "      - mascarade-network"
}
