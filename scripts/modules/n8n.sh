#!/usr/bin/env bash
# scripts/modules/n8n.sh — Module n8n

module_n8n_config() {
  N8N_PORT=$(input_value "Port n8n" "5678")
}

module_n8n_compose() {
  echo "  n8n:"
  echo "    image: n8nio/n8n:latest"
  echo "    container_name: mascarade-n8n"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${N8N_PORT}:5678\""
  echo "    environment:"
  echo "      DB_TYPE: postgresdb"
  echo "      DB_POSTGRESDB_HOST: postgres"
  echo "      DB_POSTGRESDB_PORT: 5432"
  echo "      DB_POSTGRESDB_DATABASE: mascarade"
  echo "      DB_POSTGRESDB_USER: mascarade"
  echo "      DB_POSTGRESDB_PASSWORD: \${POSTGRES_PASSWORD:-changeme}"
  if svc_selected "postgres"; then
    echo "    depends_on:"
    echo "      - postgres"
  fi
  echo "    volumes:"
  echo "      - n8n-data:/home/node/.n8n"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_n8n_volumes() {
  echo "  n8n-data:"
}
