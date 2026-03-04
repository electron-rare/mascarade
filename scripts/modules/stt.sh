#!/usr/bin/env bash
# scripts/modules/stt.sh — Module STT (multi-engine Whisper)

module_stt_config() {
  STT_PORT=$(input_value "Port STT" "${STT_PORT:-9001}")
  STT_ENGINE=$(input_value "Moteur STT (openai_whisper|faster_whisper)" "${STT_ENGINE:-faster_whisper}")
  STT_MODEL=$(input_value "Modele STT (tiny/base/small/medium/large)" "${STT_MODEL:-small}")
}

module_stt_compose() {
  local engine
  engine="$(echo "${STT_ENGINE:-faster_whisper}" | tr '[:upper:]' '[:lower:]')"

  echo "  stt:"
  echo "    image: onerahmet/openai-whisper-asr-webservice:latest"
  echo "    container_name: mascarade-stt"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${STT_PORT}:9000\""
  echo "    environment:"
  case "$engine" in
    openai_whisper)
      echo "      ASR_ENGINE: openai_whisper"
      ;;
    faster_whisper|*)
      echo "      ASR_ENGINE: faster_whisper"
      ;;
  esac
  echo "      STT_ENGINE: \${STT_ENGINE:-faster_whisper}"
  echo "      ASR_MODEL: \${STT_MODEL:-small}"
  echo "    volumes:"
  echo "      - stt-cache:/root/.cache"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_stt_volumes() {
  echo "  stt-cache:"
}
