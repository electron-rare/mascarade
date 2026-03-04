#!/usr/bin/env bash
# scripts/modules/generate-audio.sh — Module API audio generation (AudioGen/MusicGen)

module_generate_audio_config() {
  GENERATE_AUDIO_PORT=$(input_value "Port Generate Audio" "${GENERATE_AUDIO_PORT:-9000}")
  GENERATE_AUDIO_ENGINE=$(input_value "Moteur audio (audiogen|musicgen)" "${GENERATE_AUDIO_ENGINE:-audiogen}")
  GENERATE_AUDIO_MODEL=$(input_value "Modele audio (ex: facebook/audiogen-medium)" "${GENERATE_AUDIO_MODEL:-facebook/audiogen-medium}")
  GENERATE_AUDIO_RUNTIME=$(input_value "Runtime audio (auto|cpu|cuda)" "${GENERATE_AUDIO_RUNTIME:-auto}")
}

module_generate_audio_compose() {
  local engine
  local runtime
  engine="$(echo "${GENERATE_AUDIO_ENGINE:-audiogen}" | tr '[:upper:]' '[:lower:]')"
  runtime="$(echo "${GENERATE_AUDIO_RUNTIME:-auto}" | tr '[:upper:]' '[:lower:]')"

  echo "  generate-audio:"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.generate-audio"
  echo "    container_name: mascarade-generate-audio"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${GENERATE_AUDIO_PORT}:9000\""
  if [[ "$runtime" == "cuda" ]]; then
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
  echo "      HF_HOME: /root/.cache/huggingface"
  echo "    volumes:"
  echo "      - generate-audio-cache:/root/.cache/huggingface"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_generate_audio_volumes() {
  echo "  generate-audio-cache:"
}
