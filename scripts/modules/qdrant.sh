#!/usr/bin/env bash
# scripts/modules/qdrant.sh — Module Qdrant

module_qdrant_config() {
  QDRANT_PORT=$(input_value "Qdrant port" "${QDRANT_PORT:-6333}")
}

module_qdrant_compose() {
  echo "  qdrant:"
  echo "    image: \${QDRANT_IMAGE:-qdrant/qdrant@sha256:f1c7272cdac52b38c1a0e89313922d940ba50afd90d593a1605dbbc214e66ffb}"
  echo "    container_name: mascarade-qdrant"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${QDRANT_PORT}:6333\""
  echo "    volumes:"
  echo "      - qdrant-data:/qdrant/storage"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"curl -fsS http://localhost:6333/healthz >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 5"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_qdrant_volumes() {
  echo "  qdrant-data:"
}
