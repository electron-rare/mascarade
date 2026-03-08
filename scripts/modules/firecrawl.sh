#!/usr/bin/env bash
# scripts/modules/firecrawl.sh — Module Firecrawl MCP

module_firecrawl_config() {
  FIRECRAWL_PORT=$(input_value "Port Firecrawl MCP" "${FIRECRAWL_PORT:-3400}")
  FIRECRAWL_HOST=$(input_value "Host Firecrawl MCP" "${FIRECRAWL_HOST:-0.0.0.0}")
  FIRECRAWL_API_KEY=$(input_optional_secret "Firecrawl API key" "${FIRECRAWL_API_KEY:-}")
  FIRECRAWL_API_URL=$(input_optional_value "Firecrawl API URL (self-host optionnel)" "${FIRECRAWL_API_URL:-}")
}

module_firecrawl_compose() {
  cat <<'EOF'
  firecrawl:
    image: ${FIRECRAWL_IMAGE:-mcp/firecrawl@sha256:e6676bd31d1806574d931b7a7b7b6fba953c031853e80adc1ec8115c17ab81ca}
    container_name: mascarade-firecrawl
    restart: unless-stopped
    ports:
      - "${PUBLISH_BIND_HOST:-0.0.0.0}:${FIRECRAWL_PORT:-3400}:3000"
    env_file:
      - .env
    environment:
      HTTP_STREAMABLE_SERVER: "true"
      PORT: 3000
      HOST: ${FIRECRAWL_HOST:-0.0.0.0}
      FIRECRAWL_API_KEY: ${FIRECRAWL_API_KEY:-}
      FIRECRAWL_API_URL: ${FIRECRAWL_API_URL:-}
    healthcheck:
      test: ["CMD-SHELL", "node -e \"if (!process.env.FIRECRAWL_API_KEY && !process.env.FIRECRAWL_API_URL) process.exit(1); const net = require('net'); const socket = net.connect(3000, '127.0.0.1'); socket.on('connect', () => { socket.end(); process.exit(0); }); socket.on('error', () => process.exit(1)); setTimeout(() => process.exit(1), 3000);\""]
      interval: 15s
      timeout: 5s
      retries: 10
      start_period: 20s
    networks:
      - mascarade-network
EOF
}

module_firecrawl_volumes() {
  :
}
