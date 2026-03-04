#!/usr/bin/env bash
# scripts/modules/ollama.sh — Module Ollama

module_ollama_config() {
  input_value "OLLAMA_PORT" "Ollama port" "11434"
}

module_ollama_compose() {
  echo "  ollama:"
  echo "    image: ollama/ollama:latest"
  echo "    container_name: mascarade-ollama"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${OLLAMA_PORT}:11434\""
  echo "    volumes:"
  echo "      - ollama-data:/root/.ollama"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_ollama_volumes() {
  echo "  ollama-data:"
}
