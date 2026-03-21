#!/usr/bin/env bash
# scripts/modules/ollama.sh — Module Ollama

module_ollama_config() {
  local default_port="${OLLAMA_PORT:-11434}"
  local default_publish="${OLLAMA_PUBLISH_PORT:-true}"
  local default_models_dir="${OLLAMA_HOST_MODELS_DIR:-}"
  local default_use_gpu="${OLLAMA_USE_GPU:-false}"

  if host_has_nvidia_gpu; then
    default_use_gpu="${OLLAMA_USE_GPU:-true}"
  fi

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
  OLLAMA_USE_GPU=$(input_value "Activer le GPU NVIDIA pour Ollama (true|false)" "$default_use_gpu")
  OLLAMA_HOST_MODELS_DIR=$(input_value "Dossier host des modeles Ollama (optionnel)" "$default_models_dir")
}

module_ollama_compose() {
  echo "  ollama:"
  echo "    profiles:"
  echo "      - fine-tuning"
  echo "    image: \${OLLAMA_IMAGE:-ollama/ollama@sha256:719122581b6932e1240ae70d788859089cb80d17e23cd4f98ba960b0290f70cb}"
  echo "    container_name: mascarade-ollama"
  echo "    restart: unless-stopped"
  if [[ "${OLLAMA_USE_GPU:-false}" == "true" ]]; then
    echo "    gpus: all"
    echo "    deploy:"
    echo "      resources:"
    echo "        reservations:"
    echo "          devices:"
    echo "            - driver: nvidia"
    echo "              count: all"
    echo "              capabilities: [gpu]"
  fi
  if [[ "${OLLAMA_PUBLISH_PORT:-true}" == "true" ]]; then
    echo "    ports:"
    echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OLLAMA_PORT}:11434\""
  fi
  if [[ "${OLLAMA_USE_GPU:-false}" == "true" ]]; then
    echo "    environment:"
    echo "      NVIDIA_VISIBLE_DEVICES: all"
    echo "      NVIDIA_DRIVER_CAPABILITIES: compute,utility"
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
