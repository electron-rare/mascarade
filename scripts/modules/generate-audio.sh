#!/usr/bin/env bash
# scripts/modules/generate-audio.sh — Module API audio (multi-engine Whisper)

module_generate_audio_config() {
  GENERATE_AUDIO_PORT=$(input_value "Port Generate Audio" "${GENERATE_AUDIO_PORT:-9000}")
  GENERATE_AUDIO_ENGINE=$(input_value "Moteur audio (openai_whisper|faster_whisper)" "${GENERATE_AUDIO_ENGINE:-faster_whisper}")
  GENERATE_AUDIO_MODEL=$(input_value "Modele audio (tiny/base/small/medium/large)" "${GENERATE_AUDIO_MODEL:-small}")
}

module_generate_audio_compose() {
  local engine
  engine="$(echo "${GENERATE_AUDIO_ENGINE:-faster_whisper}" | tr '[:upper:]' '[:lower:]')"

  echo "  generate-audio:"
  echo "    image: onerahmet/openai-whisper-asr-webservice:latest"
  echo "    container_name: mascarade-generate-audio"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${GENERATE_AUDIO_PORT}:9000\""
  echo "    environment:"
  case "$engine" in
    openai_whisper)
      echo "      ASR_ENGINE: openai_whisper"
      ;;
    faster_whisper|*)
      echo "      ASR_ENGINE: faster_whisper"
      ;;
  esac
  echo "      GENERATE_AUDIO_ENGINE: \${GENERATE_AUDIO_ENGINE:-faster_whisper}"
  echo "      ASR_MODEL: \${GENERATE_AUDIO_MODEL:-small}"
  echo "    volumes:"
  echo "      - generate-audio-cache:/root/.cache"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_generate_audio_volumes() {
  echo "  generate-audio-cache:"
}
