#!/usr/bin/env bash
# scripts/modules/langfuse.sh — Module Langfuse

module_langfuse_config() {
  LANGFUSE_PORT=$(input_value "Port Langfuse" "${LANGFUSE_PORT:-3200}")
  LANGFUSE_INIT_PROJECT_PUBLIC_KEY=$(input_secret "Langfuse init public key" "${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-pk-lf-$(openssl rand -hex 32)}")
  LANGFUSE_INIT_PROJECT_SECRET_KEY=$(input_secret "Langfuse init secret key" "${LANGFUSE_INIT_PROJECT_SECRET_KEY:-sk-lf-$(openssl rand -hex 32)}")
  ENCRYPTION_KEY=$(input_secret "Encryption key" "${ENCRYPTION_KEY:-$(openssl rand -hex 32)}")
  NEXTAUTH_SECRET=$(input_secret "NextAuth secret" "${NEXTAUTH_SECRET:-$(openssl rand -hex 32)}")
  SALT=$(input_secret "Salt" "${SALT:-$(openssl rand -hex 32)}")
  LANGFUSE_PUBLIC_ORIGIN=$(input_value "Langfuse public origin" "${LANGFUSE_PUBLIC_ORIGIN:-https://langfuse.localhost}")
  NEXTAUTH_URL=$(input_value "NextAuth URL" "${NEXTAUTH_URL:-${LANGFUSE_PUBLIC_ORIGIN}}")
  MINIO_ROOT_USER=$(input_value "MinIO root user" "${MINIO_ROOT_USER:-minio}")
  MINIO_ROOT_PASSWORD=$(input_secret "MinIO root password" "${MINIO_ROOT_PASSWORD:-$(openssl rand -hex 24)}")
  CLICKHOUSE_PASSWORD=$(input_secret "ClickHouse password" "${CLICKHOUSE_PASSWORD:-$(openssl rand -hex 24)}")
}

module_langfuse_compose() {
  echo "  langfuse-worker:"
  echo "    image: \${LANGFUSE_WORKER_IMAGE:-langfuse/langfuse-worker@sha256:8bb47a4240ea293a210e460eae912ce06ea8fc2f724ce89cb146547eed36f6b2}"
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
  echo "      CLICKHOUSE_USER: \${CLICKHOUSE_USER:-langfuse}"
  echo "      CLICKHOUSE_PASSWORD: \${CLICKHOUSE_PASSWORD:-}"
  echo "      CLICKHOUSE_CLUSTER_ENABLED: \"false\""
  echo "      REDIS_CONNECTION_STRING: redis://redis:6379"
  echo "      REDIS_TLS_ENABLED: \"false\""
  echo "      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_REGION: auto"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: \${MINIO_ROOT_USER:-minio}"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: \${MINIO_ROOT_PASSWORD:-}"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000"
  echo "      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: \"true\""
  echo "      LANGFUSE_S3_EVENT_UPLOAD_PREFIX: events/"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: langfuse"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_REGION: auto"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: \${MINIO_ROOT_USER:-minio}"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY: \${MINIO_ROOT_PASSWORD:-}"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: http://minio:9000"
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: \"true\""
  echo "      LANGFUSE_S3_MEDIA_UPLOAD_PREFIX: media/"
  echo "    depends_on:"
  if svc_selected "postgres"; then
    echo "      postgres:"
    echo "        condition: service_healthy"
  fi
  if svc_selected "clickhouse"; then
    echo "      clickhouse:"
    echo "        condition: service_healthy"
  fi
  if svc_selected "redis"; then
    echo "      redis:"
    echo "        condition: service_healthy"
  fi
  echo "      minio:"
  echo "        condition: service_healthy"
  echo "    healthcheck:"
  echo "      test:"
  echo "        - CMD-SHELL"
  echo '        - IP=$$(hostname -i | awk '\''{print $$1}'\'') && wget -q --spider "http://$$IP:3030/"'
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 20s"
  echo "    networks:"
  echo "      - mascarade-network"
  echo ""

  echo "  langfuse-web:"
  echo "    image: \${LANGFUSE_WEB_IMAGE:-langfuse/langfuse@sha256:8d3211972d2a0610258ff0cc86da6b2d367f804bf253e9b94863bf961e59d23c}"
  echo "    container_name: mascarade-langfuse"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${LANGFUSE_PORT}:3000\""
  echo "    environment:"
  echo "      <<: *langfuse-worker-env"
  echo "      LANGFUSE_INIT_PROJECT_PUBLIC_KEY: \${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-}"
  echo "      LANGFUSE_INIT_PROJECT_SECRET_KEY: \${LANGFUSE_INIT_PROJECT_SECRET_KEY:-}"
  echo "      LANGFUSE_PUBLIC_ORIGIN: \${LANGFUSE_PUBLIC_ORIGIN:-http://langfuse-web:3000}"
  echo "    depends_on:"
  echo "      langfuse-worker:"
  echo "        condition: service_started"
  if svc_selected "postgres"; then
    echo "      postgres:"
    echo "        condition: service_healthy"
  fi
  if svc_selected "clickhouse"; then
    echo "      clickhouse:"
    echo "        condition: service_healthy"
  fi
  if svc_selected "redis"; then
    echo "      redis:"
    echo "        condition: service_healthy"
  fi
  echo "      minio:"
  echo "        condition: service_healthy"
  echo "    networks:"
  echo "      - mascarade-network"
  echo ""

  echo "  minio:"
  echo "    image: \${MINIO_IMAGE:-minio/minio@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e}"
  echo "    container_name: mascarade-langfuse-minio"
  echo "    restart: unless-stopped"
  echo "    entrypoint: sh"
  echo "    command: -c 'mkdir -p /data/langfuse && minio server --address \":9000\" --console-address \":9001\" /data'"
  echo "    environment:"
  echo "      MINIO_ROOT_USER: \${MINIO_ROOT_USER:-minio}"
  echo "      MINIO_ROOT_PASSWORD: \${MINIO_ROOT_PASSWORD:-}"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:9190:9000\""
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:9191:9001\""
  echo "    volumes:"
  echo "      - langfuse-minio-data:/data"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 15s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_langfuse_volumes() {
  echo "  langfuse-minio-data:"
}
