#!/usr/bin/env bash
# scripts/modules/langfuse.sh — Module Langfuse

module_langfuse_config() {
  LANGFUSE_PORT=$(input_value "Port Langfuse" "3200")
  LANGFUSE_SECRET_KEY=$(input_secret "Langfuse secret key" "${LANGFUSE_SECRET_KEY:-$(openssl rand -hex 32)}")
  LANGFUSE_NEXT_PUBLIC_KEY=$(input_secret "Langfuse public key" "${LANGFUSE_NEXT_PUBLIC_KEY:-$(openssl rand -hex 32)}")
  ENCRYPTION_KEY=$(input_secret "Encryption key" "${ENCRYPTION_KEY:-$(openssl rand -hex 32)}")
  NEXTAUTH_SECRET=$(input_secret "NextAuth secret" "${NEXTAUTH_SECRET:-$(openssl rand -hex 32)}")
  SALT=$(input_secret "Salt" "${SALT:-$(openssl rand -hex 32)}")
  NEXTAUTH_URL=$(input_value "NextAuth URL" "http://localhost:${LANGFUSE_PORT}")
}

module_langfuse_compose() {
  echo "  langfuse:"
  echo "    image: langfuse/langfuse:latest"
  echo "    container_name: mascarade-langfuse"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${LANGFUSE_PORT}:3000\""
  echo "    environment:"
  echo "      DATABASE_URL: postgresql://mascarade:\${POSTGRES_PASSWORD}@postgres:5432/mascarade"
  echo "      NEXTAUTH_URL: \${NEXTAUTH_URL}"
  echo "      NEXTAUTH_SECRET: \${NEXTAUTH_SECRET}"
  echo "      SALT: \${SALT}"
  echo "      ENCRYPTION_KEY: \${ENCRYPTION_KEY}"
  echo "      LANGFUSE_SECRET_KEY: \${LANGFUSE_SECRET_KEY}"
  echo "      LANGFUSE_NEXT_PUBLIC_KEY: \${LANGFUSE_NEXT_PUBLIC_KEY}"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_ENABLED: \"false\""
  if svc_selected "clickhouse"; then
    echo "      CLICKHOUSE_URL: http://clickhouse:8123"
  fi
  echo "    depends_on:"
  if svc_selected "postgres"; then
    echo "      - postgres"
  fi
  if svc_selected "clickhouse"; then
    echo "      - clickhouse"
  fi
  echo "    networks:"
  echo "      - mascarade-network"
}

module_langfuse_volumes() {
  :
}
