#!/usr/bin/env bash
# scripts/modules/tts.sh — Module TTS (multi-engine)

module_tts_config() {
  TTS_PORT=$(input_value "Port TTS" "${TTS_PORT:-10200}")
  TTS_ENGINE=$(input_value "Moteur TTS (piper|kokoro)" "${TTS_ENGINE:-piper}")
  TTS_VOICE=$(input_value "Voix TTS (optionnel)" "${TTS_VOICE:-}")
}

module_tts_compose() {
  local engine
  engine="$(echo "${TTS_ENGINE:-piper}" | tr '[:upper:]' '[:lower:]')"

  echo "  tts:"
  echo "    container_name: mascarade-tts"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${TTS_PORT}:10200\""

  case "$engine" in
    kokoro)
      echo "    image: \${TTS_KOKORO_IMAGE:-ghcr.io/marjocchi/wyoming-kokoro:latest}"
      ;;
    piper|*)
      echo "    image: \${TTS_PIPER_IMAGE:-rhasspy/wyoming-piper:latest}"
      ;;
  esac

  echo "    environment:"
  echo "      TTS_ENGINE: \${TTS_ENGINE:-piper}"
  echo "      TTS_VOICE: \${TTS_VOICE:-}"
  echo "    volumes:"
  echo "      - tts-data:/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_tts_volumes() {
  echo "  tts-data:"
}
