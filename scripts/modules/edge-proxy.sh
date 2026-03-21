#!/usr/bin/env bash
# scripts/modules/edge-proxy.sh — Reverse proxy HTTP/HTTPS de la stack

module_edge_proxy_config() {
  if [[ -z "${PUBLISH_BIND_HOST:-}" || "${PUBLISH_BIND_HOST}" == "0.0.0.0" ]]; then
    PUBLISH_BIND_HOST=$(input_value "Bind host services internes" "127.0.0.1")
  fi
  EDGE_PROXY_BIND_HOST=$(input_value "Bind host Edge Proxy" "${EDGE_PROXY_BIND_HOST:-0.0.0.0}")
  EDGE_PROXY_HTTP_PORT=$(input_value "Port HTTP Edge Proxy" "${EDGE_PROXY_HTTP_PORT:-80}")
  EDGE_PROXY_HTTPS_PORT=$(input_value "Port HTTPS Edge Proxy" "${EDGE_PROXY_HTTPS_PORT:-443}")
  EDGE_PROXY_SERVER_NAME=$(input_value "Server name Edge Proxy" "${EDGE_PROXY_SERVER_NAME:-saillant.cc}")
  EDGE_PROXY_TLS_SANS=$(input_value "TLS SANs Edge Proxy" "${EDGE_PROXY_TLS_SANS:-DNS:localhost,IP:127.0.0.1,DNS:saillant.cc,DNS:*.saillant.cc}")
  EDGE_PROXY_ACME_EMAIL=$(input_optional_value "Email ACME Edge Proxy" "${EDGE_PROXY_ACME_EMAIL:-}")
  EDGE_PROXY_ACME_DOMAINS=$(input_optional_value "Domaines ACME Edge Proxy (csv)" "${EDGE_PROXY_ACME_DOMAINS:-${EDGE_PROXY_SERVER_NAME:-saillant.cc},*.saillant.cc}")
  EDGE_PROXY_ACME_DNS_PROVIDER=$(input_value "Provider DNS ACME Edge Proxy" "${EDGE_PROXY_ACME_DNS_PROVIDER:-cloudflare}")
  EDGE_PROXY_ACME_CA=$(input_value "CA ACME Edge Proxy" "${EDGE_PROXY_ACME_CA:-letsencrypt}")
  EDGE_PROXY_ACME_KEY_LENGTH=$(input_value "Key length ACME Edge Proxy" "${EDGE_PROXY_ACME_KEY_LENGTH:-ec-256}")
  EDGE_PROXY_ACME_DNS_SLEEP=$(input_value "DNS sleep ACME Edge Proxy (s)" "${EDGE_PROXY_ACME_DNS_SLEEP:-30}")
  EDGE_PROXY_GRAFANA_SERVER_NAME=$(input_value "Server name Grafana via proxy" "${EDGE_PROXY_GRAFANA_SERVER_NAME:-grafana.saillant.cc}")
  EDGE_PROXY_LANGFUSE_SERVER_NAME=$(input_value "Server name Langfuse via proxy" "${EDGE_PROXY_LANGFUSE_SERVER_NAME:-langfuse.saillant.cc}")
  EDGE_PROXY_OLLAMA_SERVER_NAME=$(input_value "Server name Ollama via proxy" "${EDGE_PROXY_OLLAMA_SERVER_NAME:-ollama.saillant.cc}")
  EDGE_PROXY_PROMETHEUS_SERVER_NAME=$(input_value "Server name Prometheus via proxy" "${EDGE_PROXY_PROMETHEUS_SERVER_NAME:-prometheus.saillant.cc}")
  EDGE_PROXY_MEM0_SERVER_NAME=$(input_value "Server name Mem0 via proxy" "${EDGE_PROXY_MEM0_SERVER_NAME:-mem0.saillant.cc}")
  EDGE_PROXY_FIRECRAWL_SERVER_NAME=$(input_value "Server name Firecrawl via proxy" "${EDGE_PROXY_FIRECRAWL_SERVER_NAME:-firecrawl.saillant.cc}")
  EDGE_PROXY_SEARCH_SERVER_NAME=$(input_value "Server name SearXNG via proxy" "${EDGE_PROXY_SEARCH_SERVER_NAME:-search.saillant.cc}")
  EDGE_PROXY_PAPERLESS_SERVER_NAME=$(input_value "Server name Paperless via proxy" "${EDGE_PROXY_PAPERLESS_SERVER_NAME:-paperless.saillant.cc}")
  EDGE_PROXY_KARAKEEP_SERVER_NAME=$(input_value "Server name Karakeep via proxy" "${EDGE_PROXY_KARAKEEP_SERVER_NAME:-karakeep.saillant.cc}")
  EDGE_PROXY_ZEROCLAW_SERVER_NAME=$(input_value "Server name ZeroClaw via proxy" "${EDGE_PROXY_ZEROCLAW_SERVER_NAME:-zeroclaw.saillant.cc}")
  EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME=$(input_value "Server name ZeroClaw docs via proxy" "${EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME:-zeroclaw-docs.saillant.cc}")
  EDGE_PROXY_LANGGRAPH_SERVER_NAME=$(input_value "Server name LangGraph via proxy" "${EDGE_PROXY_LANGGRAPH_SERVER_NAME:-langgraph.saillant.cc}")
  EDGE_PROXY_INDUSTRIAL_SERVER_NAME=$(input_value "Server name cockpit industriel via proxy" "${EDGE_PROXY_INDUSTRIAL_SERVER_NAME:-industrial.saillant.cc}")
  EDGE_PROXY_OPS_AUTH_USER=$(input_value "Basic auth user ops tools" "${EDGE_PROXY_OPS_AUTH_USER:-ops}")
  EDGE_PROXY_OPS_AUTH_PASSWORD=$(input_secret "Basic auth password ops tools" "${EDGE_PROXY_OPS_AUTH_PASSWORD:-$(openssl rand -hex 16)}")
  CLOUDFLARE_API_TOKEN=$(input_optional_secret "Token API Cloudflare" "${CLOUDFLARE_API_TOKEN:-}")
}

module_edge_proxy_compose() {
  echo "  edge-proxy:"
  echo "    profiles:"
  echo "      - industrial"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.edge-proxy"
  echo "    container_name: mascarade-edge-proxy"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${EDGE_PROXY_BIND_HOST:-0.0.0.0}:\${EDGE_PROXY_HTTP_PORT}:80\""
  echo "      - \"\${EDGE_PROXY_BIND_HOST:-0.0.0.0}:\${EDGE_PROXY_HTTPS_PORT}:443\""
  echo "    env_file:"
  echo "      - .env"
  echo "    extra_hosts:"
  echo "      - \"host.docker.internal:host-gateway\""
  echo "    volumes:"
  echo "      - edge-proxy-certs:/etc/nginx/certs"
  echo "      - edge-proxy-auth:/etc/nginx/auth"
  echo "      - ../Kill_LIFE/tools/ai/integrations:/srv/kill-life/integrations:ro"
  echo "    depends_on:"
  echo "      api:"
  echo "        condition: service_started"
  echo "    healthcheck:"
  echo "      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1/healthz >/dev/null\"]"
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 10s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_edge_proxy_volumes() {
  echo "  edge-proxy-certs:"
  echo "    name: mascarade-edge-proxy-certs"
  echo "  edge-proxy-acme:"
  echo "    name: mascarade-edge-proxy-acme"
  echo "  edge-proxy-auth:"
  echo "    name: mascarade-edge-proxy-auth"
}
