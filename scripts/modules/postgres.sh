#!/usr/bin/env bash
# scripts/modules/postgres.sh — Module PostgreSQL

module_postgres_config() {
  POSTGRES_PORT=$(input_value "PostgreSQL port" "${POSTGRES_PORT:-5432}")
  POSTGRES_USER=$(input_value "PostgreSQL user" "${POSTGRES_USER:-mascarade}")
  POSTGRES_PASSWORD=$(input_secret "PostgreSQL password" "${POSTGRES_PASSWORD:-$(openssl rand -hex 24 2>/dev/null || head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \\n')}")
  POSTGRES_DB=$(input_value "PostgreSQL database" "${POSTGRES_DB:-mascarade}")
}

module_postgres_compose() {
  echo "  postgres:"
  echo "    image: \${POSTGRES_IMAGE:-postgres@sha256:20edbde7749f822887a1a022ad526fde0a47d6b2be9a8364433605cf65099416}"
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
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"pg_isready -U \${POSTGRES_USER} -d \${POSTGRES_DB}\"]"
  echo "      interval: 10s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 20s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_postgres_volumes() {
  echo "  postgres-data:"
}
