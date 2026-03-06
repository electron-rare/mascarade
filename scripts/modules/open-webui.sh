#!/usr/bin/env bash
# scripts/modules/open-webui.sh — Module Open WebUI

module_open_webui_config() {
  OPEN_WEBUI_PORT=$(input_value "Port Open WebUI" "${OPEN_WEBUI_PORT:-8080}")
}

module_open_webui_compose() {
  echo "  open-webui:"
  echo "    image: \${OPEN_WEBUI_IMAGE:-ghcr.io/open-webui/open-webui@sha256:bb3f0281554bf05a9d505ffb5a5f067ab53e13ac772eb4ea3077a92ddc64600e}"
  echo "    container_name: mascarade-open-webui"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${OPEN_WEBUI_PORT}:8080\""
  if svc_selected "ollama"; then
    echo "    depends_on:"
    echo "      ollama:"
    echo "        condition: service_healthy"
  fi
  echo "    environment:"
  echo "      OLLAMA_BASE_URL: \${OLLAMA_BASE_URL:-http://ollama:11434}"
  echo "    volumes:"
  echo "      - open-webui-data:/app/backend/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_open_webui_volumes() {
  echo "  open-webui-data:"
}
