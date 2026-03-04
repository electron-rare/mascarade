#!/usr/bin/env bash
# scripts/modules/stt.sh — Module STT (Whisper ASR)

module_stt_config() {
  STT_PORT=$(input_value "Port STT" "${STT_PORT:-9001}")
  STT_MODEL=$(input_value "Modele STT (tiny/base/small/medium/large)" "${STT_MODEL:-small}")
}

module_stt_compose() {
  echo "  stt:"
  echo "    image: onerahmet/openai-whisper-asr-webservice:latest"
  echo "    container_name: mascarade-stt"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${STT_PORT}:9000\""
  echo "    environment:"
  echo "      ASR_ENGINE: openai_whisper"
  echo "      ASR_MODEL: \${STT_MODEL:-small}"
  echo "    volumes:"
  echo "      - stt-cache:/root/.cache"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_stt_volumes() {
  echo "  stt-cache:"
}
