#!/usr/bin/env bash
# scripts/modules/langfuse.sh — Module Langfuse

module_langfuse_config() {
  LANGFUSE_PORT=$(input_value "Port Langfuse" "3200")
  LANGFUSE_INIT_PROJECT_PUBLIC_KEY=$(input_secret "Langfuse init public key" "${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-pk-lf-$(openssl rand -hex 32)}")
  LANGFUSE_INIT_PROJECT_SECRET_KEY=$(input_secret "Langfuse init secret key" "${LANGFUSE_INIT_PROJECT_SECRET_KEY:-sk-lf-$(openssl rand -hex 32)}")
  ENCRYPTION_KEY=$(input_secret "Encryption key" "${ENCRYPTION_KEY:-$(openssl rand -hex 32)}")
  NEXTAUTH_SECRET=$(input_secret "NextAuth secret" "${NEXTAUTH_SECRET:-$(openssl rand -hex 32)}")
  SALT=$(input_secret "Salt" "${SALT:-$(openssl rand -hex 32)}")
  NEXTAUTH_URL=$(input_value "NextAuth URL" "http://localhost:${LANGFUSE_PORT}")
}

module_langfuse_compose() {
  echo "  langfuse-worker:"
  echo "    image: langfuse/langfuse-worker:3"
  echo "    container_name: mascarade-langfuse-worker"
  echo "    restart: unless-stopped"
  echo "    environment: &langfuse-worker-env"
  echo "      NEXTAUTH_URL: \${NEXTAUTH_URL}"
  echo "      DATABASE_URL: postgresql://mascarade:\${POSTGRES_PASSWORD}@postgres:5432/langfuse"
  echo "      SALT: \${SALT}"
  echo "      ENCRYPTION_KEY: \${ENCRYPTION_KEY}"
  echo "      NEXTAUTH_SECRET: \${NEXTAUTH_SECRET}"
  echo "      TELEMETRY_ENABLED: \"true\""
  echo "      LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES: \"false\""
  echo "      CLICKHOUSE_URL: http://clickhouse:8123"
  echo "      CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000"
  echo "      CLICKHOUSE_USER: langfuse"
  echo "      CLICKHOUSE_PASSWORD: langfuse"
  echo "      CLICKHOUSE_CLUSTER_ENABLED: \"false\""
  echo "      REDIS_HOST: redis"
  echo "      REDIS_PORT: 6379"
  echo "      REDIS_TLS_ENABLED: \"false\""
  echo "      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_REGION: auto"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: minio"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: miniosecret"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: \"true\""
  echo "      LANGFUSE_S3_EVENT_UPLOAD_PREFIX: events/"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: langfuse"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_REGION: auto"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: minio"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY: miniosecret"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: http://minio:9000"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: \"true\""
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_PREFIX: media/"
  echo "    depends_on:"
  if svc_selected "postgres"; then
    echo "      - postgres"
  fi
  if svc_selected "clickhouse"; then
    echo "      - clickhouse"
  fi
  if svc_selected "redis"; then
    echo "      - redis"
  fi
  echo "      - minio"
  echo "    networks:"
  echo "      - mascarade-network"
  echo ""

  echo "  langfuse-web:"
  echo "    image: langfuse/langfuse:3"
  echo "    container_name: mascarade-langfuse"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${LANGFUSE_PORT}:3000\""
  echo "    environment:"
  echo "      <<: *langfuse-worker-env"
  echo "      LANGFUSE_INIT_PROJECT_PUBLIC_KEY: \${LANGFUSE_INIT_PROJECT_PUBLIC_KEY}"
  echo "      LANGFUSE_INIT_PROJECT_SECRET_KEY: \${LANGFUSE_INIT_PROJECT_SECRET_KEY}"
  echo "    depends_on:"
  echo "      - langfuse-worker"
  if svc_selected "postgres"; then
    echo "      - postgres"
  fi
  if svc_selected "clickhouse"; then
    echo "      - clickhouse"
  fi
  if svc_selected "redis"; then
    echo "      - redis"
  fi
  echo "      - minio"
  echo "    networks:"
  echo "      - mascarade-network"
  echo ""

  echo "  minio:"
  echo "    image: minio/minio:latest"
  echo "    container_name: mascarade-langfuse-minio"
  echo "    restart: unless-stopped"
  echo "    entrypoint: sh"
  echo "    command: -c 'mkdir -p /data/langfuse && minio server --address \":9000\" --console-address \":9001\" /data'"
  echo "    environment:"
  echo "      MINIO_ROOT_USER: minio"
  echo "      MINIO_ROOT_PASSWORD: miniosecret"
  echo "    ports:"
  echo "      - \"127.0.0.1:9190:9000\""
  echo "      - \"127.0.0.1:9191:9001\""
  echo "    volumes:"
  echo "      - langfuse-minio-data:/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_langfuse_volumes() {
  echo "  langfuse-minio-data:"
}
