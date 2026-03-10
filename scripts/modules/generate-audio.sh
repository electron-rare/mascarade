#!/usr/bin/env bash
# scripts/modules/generate-audio.sh — Module API audio generation (AudioGen/MusicGen)

_module_generate_audio_build_variant() {
  local runtime
  runtime="$(echo "${GENERATE_AUDIO_RUNTIME:-auto}" | tr '[:upper:]' '[:lower:]')"
  case "$runtime" in
    cpu)
      echo "cpu"
      ;;
    cuda)
      if docker_can_use_nvidia_gpu; then
        echo "cuda"
      else
        echo "cpu"
      fi
      ;;
    auto|*)
      if docker_can_use_nvidia_gpu; then
        echo "cuda"
      else
        echo "cpu"
      fi
      ;;
  esac
}

module_generate_audio_preflight() {
  local build_variant
  local requested_runtime
  local docker_root
  local check_path
  local free_gb

  build_variant="$(_module_generate_audio_build_variant)"
  requested_runtime="$(echo "${GENERATE_AUDIO_RUNTIME:-auto}" | tr '[:upper:]' '[:lower:]')"

  if [[ "$build_variant" == "cuda" ]]; then
    info "Generate Audio: profil GPU active (PyTorch CUDA 11.8 + AudioCraft)"
  else
    if [[ "$requested_runtime" == "cuda" ]]; then
      warn "Generate Audio: runtime cuda demande mais Docker ne peut pas exposer un GPU NVIDIA."
      warn "Fallback automatique en CPU pour eviter l'echec 'could not select device driver nvidia'."
    elif host_has_nvidia_gpu && ! docker_has_nvidia_runtime; then
      warn "Generate Audio: GPU NVIDIA detecte sur l'hote, mais runtime NVIDIA absent dans Docker."
      warn "Fallback automatique en CPU. Installe nvidia-container-toolkit pour activer le GPU."
    fi
    info "Generate Audio: profil CPU active (AudioCraft sans GPU)"
  fi

  if command -v docker &>/dev/null; then
    docker_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
  fi

  check_path="${docker_root:-$REPO_DIR}"
  if [[ -n "$check_path" ]] && [[ -e "$check_path" ]]; then
    # BSD/macOS `df` does not support `-B`, so use POSIX `-P` and convert blocks -> GB.
    local available_kb
    available_kb="$(df -P "$check_path" 2>/dev/null | awk 'NR==2 {print $4}')"
    if [[ -n "${available_kb:-}" ]] && [[ "$available_kb" =~ ^[0-9]+$ ]]; then
      free_gb="$((available_kb / 1024 / 1024))"
    else
      free_gb=""
    fi
    if [[ -z "$free_gb" ]]; then
      free_gb="$(df -P "$check_path" 2>/dev/null | awk 'NR==2 {sub(/G$/,"", $4); print $4}' | tr -d '[:space:]')"
      if ! [[ "$free_gb" =~ ^[0-9]+$ ]]; then
        free_gb=""
      fi
    fi
    if [[ -n "$free_gb" ]] && [[ "$free_gb" =~ ^[0-9]+$ ]]; then
      if [[ "$build_variant" == "cuda" && "$free_gb" -lt 25 ]]; then
        warn "Generate Audio CUDA: espace libre faible (${free_gb}G) sur ${check_path}."
        warn "Prevois idealement 25G+ libres pour le build et l'image finale GPU."
      elif [[ "$build_variant" == "cpu" && "$free_gb" -lt 10 ]]; then
        warn "Generate Audio CPU: espace libre faible (${free_gb}G) sur ${check_path}."
      fi
    fi
  fi
}

module_generate_audio_config() {
  local default_runtime="auto"
  if docker_can_use_nvidia_gpu; then
    default_runtime="cuda"
  fi
  GENERATE_AUDIO_PORT=$(input_value "Port Generate Audio" "${GENERATE_AUDIO_PORT:-9000}")
  GENERATE_AUDIO_ENGINE=$(input_value "Moteur audio (audiogen|musicgen)" "${GENERATE_AUDIO_ENGINE:-audiogen}")
  GENERATE_AUDIO_MODEL=$(input_value "Modele audio (ex: facebook/audiogen-medium)" "${GENERATE_AUDIO_MODEL:-facebook/audiogen-medium}")
  GENERATE_AUDIO_RUNTIME=$(input_value "Runtime audio (auto|cpu|cuda)" "${GENERATE_AUDIO_RUNTIME:-$default_runtime}")
}

module_generate_audio_compose() {
  local engine
  local runtime
  local build_variant
  local torch_index_url
  engine="$(echo "${GENERATE_AUDIO_ENGINE:-audiogen}" | tr '[:upper:]' '[:lower:]')"
  runtime="$(echo "${GENERATE_AUDIO_RUNTIME:-auto}" | tr '[:upper:]' '[:lower:]')"
  build_variant="$(_module_generate_audio_build_variant)"
  torch_index_url="https://download.pytorch.org/whl/cpu"
  if [[ "$build_variant" == "cuda" ]]; then
    torch_index_url="https://download.pytorch.org/whl/cu118"
  fi

  echo "  generate-audio:"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.generate-audio"
  echo "      args:"
  echo "        TORCH_INDEX_URL: ${GENERATE_AUDIO_TORCH_INDEX_URL:-$torch_index_url}"
  echo "        TORCH_VERSION: ${GENERATE_AUDIO_TORCH_VERSION:-2.1.0}"
  echo "        TORCHAUDIO_VERSION: ${GENERATE_AUDIO_TORCHAUDIO_VERSION:-2.1.0}"
  echo "        TORCHVISION_VERSION: ${GENERATE_AUDIO_TORCHVISION_VERSION:-0.16.0}"
  echo "        TORCHTEXT_VERSION: ${GENERATE_AUDIO_TORCHTEXT_VERSION:-0.16.0}"
  echo "        XFORMERS_VERSION: ${GENERATE_AUDIO_XFORMERS_VERSION:-0.0.22.post7}"
  echo "        AUDIOCRAFT_VERSION: ${GENERATE_AUDIOCRAFT_VERSION:-1.3.0}"
  echo "    container_name: mascarade-generate-audio"
  echo "    restart: unless-stopped"
  echo "    ports:"
      echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${GENERATE_AUDIO_PORT}:9000\""
  if [[ "$build_variant" == "cuda" ]]; then
    echo "    gpus: all"
    echo "    deploy:"
    echo "      resources:"
    echo "        reservations:"
    echo "          devices:"
    echo "            - driver: nvidia"
    echo "              count: all"
    echo "              capabilities: [gpu]"
  fi
  echo "    environment:"
  case "$engine" in
    musicgen)
      echo "      GENERATE_AUDIO_ENGINE: musicgen"
      ;;
    audiogen|*)
      echo "      GENERATE_AUDIO_ENGINE: audiogen"
      ;;
  esac
  echo "      GENERATE_AUDIO_MODEL: \${GENERATE_AUDIO_MODEL:-facebook/audiogen-medium}"
  echo "      GENERATE_AUDIO_RUNTIME: $build_variant"
  echo "      GENERATE_AUDIO_TORCH_VARIANT: $build_variant"
  echo "      GENERATE_AUDIO_KEEP_LOADED: \${GENERATE_AUDIO_KEEP_LOADED:-false}"
  echo "      GENERATE_AUDIO_IDLE_UNLOAD_SECONDS: \${GENERATE_AUDIO_IDLE_UNLOAD_SECONDS:-0}"
  if [[ "$build_variant" == "cuda" ]]; then
    echo "      NVIDIA_VISIBLE_DEVICES: all"
    echo "      NVIDIA_DRIVER_CAPABILITIES: compute,utility"
  fi
  echo "      HF_HOME: /root/.cache/huggingface"
  echo "    volumes:"
      echo "      - generate-audio-cache:/root/.cache/huggingface"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_generate_audio_volumes() {
  echo "  generate-audio-cache:"
}
