#!/usr/bin/env bash
# scripts/modules/ollama.sh — Module Ollama

module_ollama_config() {
  local default_port="${OLLAMA_PORT:-11434}"
  local default_publish="${OLLAMA_PUBLISH_PORT:-true}"
  local default_models_dir="${OLLAMA_HOST_MODELS_DIR:-}"

  if [[ -z "${OLLAMA_HOST_MODELS_DIR:-}" ]]; then
    for candidate in /usr/share/ollama/.ollama /var/lib/ollama/.ollama; do
      if [[ -d "$candidate" ]]; then
        default_models_dir="$candidate"
        break
      fi
    done
  fi

  if [[ -z "${OLLAMA_PUBLISH_PORT:-}" ]] && ! port_available "$default_port"; then
    default_publish="false"
  fi

  OLLAMA_PORT=$(input_value "Ollama port" "$default_port")
  OLLAMA_PUBLISH_PORT=$(input_value "Publier Ollama sur l'hote (true|false)" "$default_publish")
  OLLAMA_HOST_MODELS_DIR=$(input_value "Dossier host des modeles Ollama (optionnel)" "$default_models_dir")
}

module_ollama_compose() {
  echo "  ollama:"
  echo "    image: \${OLLAMA_IMAGE:-ollama/ollama@sha256:719122581b6932e1240ae70d788859089cb80d17e23cd4f98ba960b0290f70cb}"
  echo "    container_name: mascarade-ollama"
  echo "    restart: unless-stopped"
  if [[ "${OLLAMA_PUBLISH_PORT:-true}" == "true" ]]; then
    echo "    ports:"
    echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OLLAMA_PORT}:11434\""
  fi
  echo "    volumes:"
  if [[ -n "${OLLAMA_HOST_MODELS_DIR:-}" ]]; then
    echo "      - \${OLLAMA_HOST_MODELS_DIR}:/root/.ollama:ro"
  else
    echo "      - ollama-data:/root/.ollama"
  fi
  echo "    healthcheck:"
  echo '      test: ["CMD-SHELL", "ollama list >/dev/null 2>&1"]'
  echo "      interval: 20s"
  echo "      timeout: 10s"
  echo "      retries: 15"
  echo "      start_period: 40s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_ollama_volumes() {
  if [[ -z "${OLLAMA_HOST_MODELS_DIR:-}" ]]; then
    echo "  ollama-data:"
  fi
}
