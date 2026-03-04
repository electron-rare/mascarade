#!/usr/bin/env bash
# scripts/modules/ops-console.sh — Module Ops Console (cockpit web)

module_ops_console_config() {
  OPS_CONSOLE_PORT=$(input_value "Port Ops Console" "${OPS_CONSOLE_PORT:-80}")
}

module_ops_console_compose() {
  echo "  ops-console:"
  echo "    image: nginx:alpine"
  echo "    container_name: mascarade-ops-console"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${OPS_CONSOLE_BIND_IP:-127.0.0.1}:\${OPS_CONSOLE_PORT}:80\""
  echo "    volumes:"
  echo "      - ./deploy/ops-console/index.html:/usr/share/nginx/html/index.html:ro"
  if svc_selected "core" || svc_selected "api" || svc_selected "open-webui" || svc_selected "grafana" || svc_selected "prometheus" || svc_selected "ollama"; then
    echo "    depends_on:"
    svc_selected "core" && echo "      - core"
    svc_selected "api" && echo "      - api"
    svc_selected "open-webui" && echo "      - open-webui"
    svc_selected "grafana" && echo "      - grafana"
    svc_selected "prometheus" && echo "      - prometheus"
    svc_selected "ollama" && echo "      - ollama"
  fi
  echo "    networks:"
  echo "      - mascarade-network"
}
