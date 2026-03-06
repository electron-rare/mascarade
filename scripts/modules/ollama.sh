#!/usr/bin/env bash
# scripts/modules/ollama.sh — Module Ollama

module_ollama_config() {
  OLLAMA_PORT=$(input_value "Ollama port" "${OLLAMA_PORT:-11434}")
}

module_ollama_compose() {
  echo "  ollama:"
  echo "    image: \${OLLAMA_IMAGE:-ollama/ollama@sha256:719122581b6932e1240ae70d788859089cb80d17e23cd4f98ba960b0290f70cb}"
  echo "    container_name: mascarade-ollama"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OLLAMA_PORT}:11434\""
  echo "    volumes:"
  echo "      - ollama-data:/root/.ollama"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"ollama list >/dev/null 2>&1\"]"
  echo "      interval: 20s"
  echo "      timeout: 10s"
  echo "      retries: 15"
  echo "      start_period: 40s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_ollama_volumes() {
  echo "  ollama-data:"
}
