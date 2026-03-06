#!/usr/bin/env bash
# scripts/modules/generate-audio.sh — Module API audio generation (AudioGen/MusicGen)

_module_generate_audio_build_variant() {
  local runtime
  runtime="$(echo "${GENERATE_AUDIO_RUNTIME:-auto}" | tr '[:upper:]' '[:lower:]')"
  case "$runtime" in
    cuda|cpu)
      echo "$runtime"
      ;;
    auto|*)
      if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
        echo "cuda"
      else
        echo "cpu"
      fi
      ;;
  esac
}

module_generate_audio_preflight() {
  local build_variant
  local docker_root
  local check_path
  local free_gb

  build_variant="$(_module_generate_audio_build_variant)"

  if [[ "$build_variant" == "cuda" ]]; then
    info "Generate Audio: profil GPU active (PyTorch CUDA 11.8 + AudioCraft)"
    if ! command -v nvidia-smi &>/dev/null || ! nvidia-smi &>/dev/null; then
      warn "Generate Audio: runtime cuda selectionne mais aucun GPU NVIDIA n'est detecte sur l'hote."
      warn "Le build passera, mais le conteneur ne pourra pas exploiter le GPU sans pilote/NVIDIA visibles."
    fi
    if command -v docker &>/dev/null; then
      if ! docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -qi 'nvidia'; then
        warn "Generate Audio: runtime NVIDIA non detecte dans Docker."
        warn "Installe nvidia-container-toolkit et verifie 'docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi'."
      fi
      docker_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
    fi
  else
    info "Generate Audio: profil CPU active (AudioCraft sans GPU)"
  fi

  check_path="${docker_root:-$REPO_DIR}"
  if [[ -n "$check_path" ]] && [[ -e "$check_path" ]]; then
    free_gb="$(df -BG "$check_path" 2>/dev/null | awk 'NR==2 {gsub(/G/, "", $4); print $4}')"
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
  if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
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
      echo "      - \"127.0.0.1:\${GENERATE_AUDIO_PORT}:9000\""
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
  echo "      GENERATE_AUDIO_RUNTIME: \${GENERATE_AUDIO_RUNTIME:-auto}"
  echo "      GENERATE_AUDIO_TORCH_VARIANT: \${GENERATE_AUDIO_TORCH_VARIANT:-$build_variant}"
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
