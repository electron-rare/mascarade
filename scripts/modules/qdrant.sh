#!/usr/bin/env bash
# scripts/modules/qdrant.sh — Module Qdrant

module_qdrant_config() {
  input_value "QDRANT_PORT" "Qdrant port" "6333"
}

module_qdrant_compose() {
  echo "  qdrant:"
  echo "    image: qdrant/qdrant:latest"
  echo "    container_name: mascarade-qdrant"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${QDRANT_PORT}:6333\""
  echo "    volumes:"
  echo "      - qdrant-data:/qdrant/storage"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_qdrant_volumes() {
  echo "  qdrant-data:"
}
