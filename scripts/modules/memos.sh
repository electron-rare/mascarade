#!/usr/bin/env bash
# scripts/modules/memos.sh — Module Memos self-hosted knowledge base

module_memos_config() {
  MEMOS_PORT=$(input_value "Port Memos" "${MEMOS_PORT:-5230}")
}

module_memos_compose() {
  cat <<'EOF'
  memos:
    image: ${MEMOS_IMAGE:-neosmemo/memos:stable}
    container_name: mascarade-memos
    restart: unless-stopped
    ports:
      - "${PUBLISH_BIND_HOST:-0.0.0.0}:${MEMOS_PORT:-5230}:5230"
    env_file:
      - .env
    environment:
      MEMOS_PORT: 5230
    volumes:
      - memos-data:/var/opt/memos
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://127.0.0.1:5230/ || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 10
      start_period: 20s
    networks:
      - mascarade-network
EOF
}

module_memos_volumes() {
  echo "  memos-data:"
}
