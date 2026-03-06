#!/usr/bin/env bash
# scripts/modules/n8n.sh — Module n8n

module_n8n_config() {
  N8N_PORT=$(input_value "Port n8n" "${N8N_PORT:-5678}")
}

module_n8n_compose() {
  echo "  n8n:"
  echo "    image: \${N8N_IMAGE:-n8nio/n8n@sha256:cfa50544c4cc172506834da1ec9bb5171db55958c8d1918205df0bda237a56f4}"
  echo "    container_name: mascarade-n8n"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${N8N_PORT}:5678\""
  echo "    environment:"
  echo "      DB_TYPE: postgresdb"
  echo "      DB_POSTGRESDB_HOST: postgres"
  echo "      DB_POSTGRESDB_PORT: 5432"
  echo "      DB_POSTGRESDB_DATABASE: mascarade"
  echo "      DB_POSTGRESDB_USER: mascarade"
  echo "      DB_POSTGRESDB_PASSWORD: \${POSTGRES_PASSWORD:-}"
  if svc_selected "postgres"; then
    echo "    depends_on:"
    echo "      postgres:"
    echo "        condition: service_healthy"
  fi
  echo "    volumes:"
  echo "      - n8n-data:/home/node/.n8n"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1:5678/healthz >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 30s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_n8n_volumes() {
  echo "  n8n-data:"
}
