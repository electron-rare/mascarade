#!/usr/bin/env bash
# scripts/modules/postgres.sh — Module PostgreSQL

module_postgres_config() {
  input_value "POSTGRES_PORT" "PostgreSQL port" "5432"
  input_value "POSTGRES_USER" "PostgreSQL user" "mascarade"
  input_secret "POSTGRES_PASSWORD" "PostgreSQL password" "secret"
  input_value "POSTGRES_DB" "PostgreSQL database" "mascarade"
}

module_postgres_compose() {
  echo "  postgres:"
  echo "    image: postgres:16-alpine"
  echo "    container_name: mascarade-postgres"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${POSTGRES_PORT}:5432\""
  echo "    environment:"
  echo "      POSTGRES_USER: \${POSTGRES_USER}"
  echo "      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}"
  echo "      POSTGRES_DB: \${POSTGRES_DB}"
  echo "    volumes:"
  echo "      - postgres-data:/var/lib/postgresql/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_postgres_volumes() {
  echo "  postgres-data:"
}
