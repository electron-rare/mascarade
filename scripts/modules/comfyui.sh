#!/usr/bin/env bash
# scripts/modules/comfyui.sh — Module ComfyUI

_module_comfyui_gpu_enabled() {
  docker_can_use_nvidia_gpu
}

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
      if _module_comfyui_gpu_enabled; then
        ok "GPU NVIDIA detecte et runtime Docker disponible"
        COMFYUI_GPU=true
      elif host_has_nvidia_gpu; then
        warn "GPU NVIDIA detecte mais runtime Docker NVIDIA absent — ComfyUI tournera en CPU"
        COMFYUI_GPU=false
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
  local comfyui_gpu=false
  [[ "${COMFYUI_LOCAL:-}" != "true" ]] && return
  if _module_comfyui_gpu_enabled; then
    comfyui_gpu=true
  fi
  echo "  comfyui:"
  echo "    profiles:"
  echo "      - fine-tuning"
  echo "    image: \${COMFYUI_IMAGE:-comfyanonymous/comfyui:latest}"
  echo "    container_name: mascarade-comfyui"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:8188:8188\""
  if [[ "$comfyui_gpu" == "true" ]]; then
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
