#!/usr/bin/env bash
# scripts/modules/mem0.sh — Module Mem0 / OpenMemory MCP

module_mem0_config() {
  MEM0_PORT=$(input_value "Port Mem0 / OpenMemory" "${MEM0_PORT:-3300}")
  MEM0_USER=$(input_value "Utilisateur Mem0 / OpenMemory" "${MEM0_USER:-mascarade}")
  MEM0_OPENAI_API_KEY=$(input_value "API key OpenAI-compatible pour Mem0" "${MEM0_OPENAI_API_KEY:-sk-mem0-local}")
  MEM0_OPENAI_BASE_URL=$(input_value "Base URL OpenAI-compatible pour Mem0" "${MEM0_OPENAI_BASE_URL:-http://litellm:4000}")
  MEM0_QDRANT_HOST=$(input_value "Hote Qdrant pour Mem0" "${MEM0_QDRANT_HOST:-qdrant}")
  MEM0_QDRANT_PORT=$(input_value "Port Qdrant pour Mem0" "${MEM0_QDRANT_PORT:-6333}")
}

module_mem0_compose() {
  cat <<'EOF'
  mem0:
    profiles:
      - personal
    image: ${MEM0_IMAGE:-mem0/openmemory-mcp:latest}
    container_name: mascarade-mem0
    restart: unless-stopped
    ports:
      - "${PUBLISH_BIND_HOST:-0.0.0.0}:${MEM0_PORT:-3300}:8765"
    env_file:
      - .env
    environment:
      USER: ${MEM0_USER:-mascarade}
      OPENAI_API_KEY: ${MEM0_OPENAI_API_KEY:-sk-mem0-local}
      OPENAI_API_BASE: ${MEM0_OPENAI_BASE_URL:-http://litellm:4000}
      OPENAI_BASE_URL: ${MEM0_OPENAI_BASE_URL:-http://litellm:4000}
      QDRANT_HOST: ${MEM0_QDRANT_HOST:-qdrant}
      QDRANT_PORT: ${MEM0_QDRANT_PORT:-6333}
    depends_on:
      litellm:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import socket; sock = socket.create_connection(('127.0.0.1', 8765), 3); sock.close()\""]
      interval: 15s
      timeout: 5s
      retries: 10
      start_period: 25s
    networks:
      - mascarade-network
EOF
}

module_mem0_volumes() {
  :
}
