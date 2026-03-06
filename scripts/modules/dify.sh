#!/usr/bin/env bash
# scripts/modules/dify.sh — Module Dify

module_dify_config() {
  DIFY_API_PORT=$(input_value "Port Dify API" "${DIFY_API_PORT:-5001}")
  DIFY_WEB_PORT=$(input_value "Port Dify Web" "${DIFY_WEB_PORT:-3500}")
}

module_dify_compose() {
  local dify_env=""
  dify_env+="      DB_USERNAME: mascarade\n"
  dify_env+="      DB_PASSWORD: \${POSTGRES_PASSWORD:-}\n"
  dify_env+="      DB_HOST: postgres\n"
  dify_env+="      DB_PORT: 5432\n"
  dify_env+="      DB_DATABASE: mascarade\n"
  dify_env+="      REDIS_HOST: redis\n"
  dify_env+="      REDIS_PORT: 6379\n"
  dify_env+="      OPENDAL_SCHEME: fs\n"
  dify_env+="      OPENDAL_ROOT: /app/api/storage\n"
  dify_env+="      OPENDAL_FS_ROOT: /app/api/storage"

  # dify-api
  echo "  dify-api:"
  echo "    image: \${DIFY_API_IMAGE:-langgenius/dify-api@sha256:5f622b4d0b39bdc6d3b401063cfb60962fa92dcc63f55daccec138f98b260e67}"
  echo "    container_name: mascarade-dify-api"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${DIFY_API_PORT}:5001\""
  echo "    environment:"
  echo -e "$dify_env"
  if svc_selected "postgres" || svc_selected "redis"; then
    echo "    depends_on:"
    if svc_selected "postgres"; then
      echo "      postgres:"
      echo "        condition: service_healthy"
    fi
    if svc_selected "redis"; then
      echo "      redis:"
      echo "        condition: service_healthy"
    fi
  fi
  echo "    networks:"
  echo "      - mascarade-network"

  # dify-web
  echo "  dify-web:"
  echo "    image: \${DIFY_WEB_IMAGE:-langgenius/dify-web@sha256:30339b4d5060488fac147ddc6fb40438ef71cd5f5dfdeb26c886768302bf7197}"
  echo "    container_name: mascarade-dify-web"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${DIFY_WEB_PORT}:3000\""
  echo "    environment:"
  echo -e "$dify_env"
  if svc_selected "postgres" || svc_selected "redis"; then
    echo "    depends_on:"
    if svc_selected "postgres"; then
      echo "      postgres:"
      echo "        condition: service_healthy"
    fi
    if svc_selected "redis"; then
      echo "      redis:"
      echo "        condition: service_healthy"
    fi
  fi
  echo "    networks:"
  echo "      - mascarade-network"

  # dify-worker
  echo "  dify-worker:"
  echo "    image: \${DIFY_API_IMAGE:-langgenius/dify-api@sha256:5f622b4d0b39bdc6d3b401063cfb60962fa92dcc63f55daccec138f98b260e67}"
  echo "    container_name: mascarade-dify-worker"
  echo "    restart: unless-stopped"
  echo "    command: celery -A app.celery worker"
  echo "    environment:"
  echo -e "$dify_env"
  if svc_selected "postgres" || svc_selected "redis"; then
    echo "    depends_on:"
    if svc_selected "postgres"; then
      echo "      postgres:"
      echo "        condition: service_healthy"
    fi
    if svc_selected "redis"; then
      echo "      redis:"
      echo "        condition: service_healthy"
    fi
  fi
  echo "    networks:"
  echo "      - mascarade-network"
}

module_dify_volumes() {
  :
}
