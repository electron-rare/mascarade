#!/usr/bin/env bash
# scripts/modules/open-webui.sh — Module Open WebUI

module_open_webui_config() {
  input_value "OPEN_WEBUI_PORT" "Open WebUI port" "8080"
}

module_open_webui_compose() {
  echo "  open-webui:"
  echo "    image: ghcr.io/open-webui/open-webui:main"
  echo "    container_name: mascarade-open-webui"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${OPEN_WEBUI_PORT}:8080\""
  if svc_selected "ollama"; then
    echo "    depends_on:"
    echo "      - ollama"
  fi
  echo "    environment:"
  echo "      OLLAMA_BASE_URL: http://ollama:11434"
  echo "    volumes:"
  echo "      - open-webui-data:/app/backend/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_open_webui_volumes() {
  echo "  open-webui-data:"
}
