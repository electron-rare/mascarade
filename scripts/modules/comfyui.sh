#!/usr/bin/env bash
# scripts/modules/comfyui.sh — Module ComfyUI

module_comfyui_config() {
  menu_select "Mode ComfyUI" \
    "Serveur distant" \
    "Installation locale (Docker)" \
    "Desactiver"

  case "$MENU_RESULT" in
    0)
      COMFYUI_URL=$(input_value "URL ComfyUI distant" "${COMFYUI_URL:-}")
      COMFYUI_LOCAL=""
      ;;
    1)
      COMFYUI_URL="http://comfyui:8188"
      COMFYUI_LOCAL=true
      # Detection GPU
      if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
        ok "GPU NVIDIA detecte"
        COMFYUI_GPU=true
      else
        warn "Pas de GPU NVIDIA detecte — ComfyUI tournera en CPU"
        COMFYUI_GPU=false
      fi
      ;;
    2)
      COMFYUI_URL=""
      COMFYUI_LOCAL=""
      ;;
  esac
}

module_comfyui_compose() {
  [[ "${COMFYUI_LOCAL:-}" != "true" ]] && return
  echo "  comfyui:"
  echo "    image: \${COMFYUI_IMAGE:-comfyanonymous/comfyui:latest}"
  echo "    container_name: mascarade-comfyui"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:8188:8188\""
  if [[ "${COMFYUI_GPU:-false}" == "true" ]]; then
    echo "    deploy:"
    echo "      resources:"
    echo "        reservations:"
    echo "          devices:"
    echo "            - driver: nvidia"
    echo "              count: all"
    echo "              capabilities: [gpu]"
  fi
  echo "    volumes:"
  echo "      - comfyui-data:/comfyui/output"
  echo "      - comfyui-models:/comfyui/models"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_comfyui_volumes() {
  [[ "${COMFYUI_LOCAL:-}" != "true" ]] && return
  echo "  comfyui-data:"
  echo "  comfyui-models:"
}
