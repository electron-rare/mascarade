#!/usr/bin/env bash
# scripts/modules/dify.sh — Module Dify

module_dify_config() {
  DIFY_API_PORT=$(input_value "Port Dify API" "5001")
  DIFY_WEB_PORT=$(input_value "Port Dify Web" "3500")
}

module_dify_compose() {
  local dify_env=""
  dify_env+="      DB_USERNAME: mascarade\n"
  dify_env+="      DB_PASSWORD: \${POSTGRES_PASSWORD:-changeme}\n"
  dify_env+="      DB_HOST: postgres\n"
  dify_env+="      DB_PORT: 5432\n"
  dify_env+="      DB_DATABASE: mascarade\n"
  dify_env+="      REDIS_HOST: redis\n"
  dify_env+="      REDIS_PORT: 6379\n"
  dify_env+="      OPENDAL_SCHEME: fs\n"
  dify_env+="      OPENDAL_ROOT: /app/api/storage\n"
  dify_env+="      OPENDAL_FS_ROOT: /app/api/storage"

  local dify_deps=""
  if svc_selected "postgres"; then
    dify_deps+="      - postgres\n"
  fi
  if svc_selected "redis"; then
    dify_deps+="      - redis\n"
  fi

  # dify-api
  echo "  dify-api:"
  echo "    image: langgenius/dify-api:latest"
  echo "    container_name: mascarade-dify-api"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${DIFY_API_PORT}:5001\""
  echo "    environment:"
  echo -e "$dify_env"
  if [[ -n "$dify_deps" ]]; then
    echo "    depends_on:"
    echo -ne "$dify_deps"
  fi
  echo "    networks:"
  echo "      - mascarade-network"

  # dify-web
  echo "  dify-web:"
  echo "    image: langgenius/dify-web:latest"
  echo "    container_name: mascarade-dify-web"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"127.0.0.1:\${DIFY_WEB_PORT}:3000\""
  echo "    environment:"
  echo -e "$dify_env"
  if [[ -n "$dify_deps" ]]; then
    echo "    depends_on:"
    echo -ne "$dify_deps"
  fi
  echo "    networks:"
  echo "      - mascarade-network"

  # dify-worker
  echo "  dify-worker:"
  echo "    image: langgenius/dify-api:latest"
  echo "    container_name: mascarade-dify-worker"
  echo "    restart: unless-stopped"
  echo "    command: celery -A app.celery worker"
  echo "    environment:"
  echo -e "$dify_env"
  if [[ -n "$dify_deps" ]]; then
    echo "    depends_on:"
    echo -ne "$dify_deps"
  fi
  echo "    networks:"
  echo "      - mascarade-network"
}

module_dify_volumes() {
  :
}
