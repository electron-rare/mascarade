#!/usr/bin/env bash
# scripts/modules/tts.sh — Module TTS (Piper/Wyoming)

module_tts_config() {
  TTS_PORT=$(input_value "Port TTS" "${TTS_PORT:-10200}")
}

module_tts_compose() {
  echo "  tts:"
  echo "    image: rhasspy/wyoming-piper:latest"
  echo "    container_name: mascarade-tts"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${TTS_PORT}:10200\""
  echo "    volumes:"
  echo "      - tts-data:/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_tts_volumes() {
  echo "  tts-data:"
}
