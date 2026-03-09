#!/usr/bin/env bash
# scripts/modules/core.sh — Module Mascarade Core

module_core_config() {
  CORE_PORT=$(input_value "Port Core" "${CORE_PORT:-8100}")
  CORE_HOST=$(input_value "Host Core" "${CORE_HOST:-0.0.0.0}")
  DEFAULT_PROVIDER=$(input_value "Provider LLM par defaut" "${DEFAULT_PROVIDER:-claude}")
  DEFAULT_MODEL=$(input_value "Modele LLM par defaut" "${DEFAULT_MODEL:-claude-sonnet-4-6}")

  if [[ "${CLUSTER_ENABLED:-false}" == "true" ]]; then
    info "Mode P2P deja actif — verification des parametres multi-noeuds"
    if [[ "${CLUSTER_MDNS_ENABLED:-false}" == "true" ]]; then
      info "Mode mDNS actif: ${CLUSTER_MDNS_SERVICE:-_mascarade._tcp.local.}"
    fi
  elif [[ ! -t 0 || ! -t 1 ]]; then
    CLUSTER_ENABLED="${CLUSTER_ENABLED:-false}"
  elif confirm "Activer le mode P2P (cluster prive) ?"; then
    CLUSTER_ENABLED=true
  else
    CLUSTER_ENABLED=false
  fi

  if [[ "${CLUSTER_ENABLED:-false}" == "true" ]]; then
    NODE_ID=$(input_value "Node ID cluster" "${NODE_ID:-node-1}")
    NODE_ROLE=$(input_value "Role du noeud cluster" "${NODE_ROLE:-general}")
    NODE_LABEL=$(input_value "Label du noeud" "${NODE_LABEL:-Mascarade Node 1}")
    MESH_BIND_HOST=$(input_value "IP mesh/VPN du noeud" "${MESH_BIND_HOST:-}")
    MESH_SCHEME=$(input_value "Scheme mesh (http/https)" "${MESH_SCHEME:-http}")
    CLUSTER_SHARED_KEY=$(input_optional_secret "Cle Bearer inter-noeuds" "${CLUSTER_SHARED_KEY:-}")
    CLUSTER_REQUEST_TIMEOUT_MS=$(input_value "Timeout cluster (ms)" "${CLUSTER_REQUEST_TIMEOUT_MS:-5000}")
    CLUSTER_HEARTBEAT_SECONDS=$(input_value "Heartbeat logique peers (s)" "${CLUSTER_HEARTBEAT_SECONDS:-30}")
    if [[ "${CLUSTER_FORWARD_ENABLED:-true}" == "true" ]]; then
      if ! confirm "Garder le forward 'core -> core' actif ?"; then
        CLUSTER_FORWARD_ENABLED=false
      fi
    else
      if confirm "Activer le forward 'core -> core' ?"; then
        CLUSTER_FORWARD_ENABLED=true
      fi
    fi
    if [[ "${CLUSTER_MDNS_ENABLED:-false}" == "true" ]]; then
      if confirm "Activer la découverte Bonjour/mDNS P2P ?"; then
        CLUSTER_MDNS_ENABLED=true
      else
        CLUSTER_MDNS_ENABLED=false
      fi
    else
      if confirm "Activer la découverte Bonjour/mDNS P2P ?"; then
        CLUSTER_MDNS_ENABLED=true
      fi
    fi
    if [[ "${CLUSTER_MDNS_ENABLED:-false}" == "true" ]]; then
      CLUSTER_MDNS_SERVICE=$(input_value "Nom service mDNS" "${CLUSTER_MDNS_SERVICE:-_mascarade._tcp.local.}")
      CLUSTER_MDNS_DISCOVERY_TTL_SECONDS=$(input_value "TTL découverte mDNS (s)" "${CLUSTER_MDNS_DISCOVERY_TTL_SECONDS:-60}")
      if [[ "${CLUSTER_MDNS_ADVERTISE:-false}" == "true" ]]; then
        if ! confirm "Publier ce noeud en mDNS (bonjour) ?"; then
          CLUSTER_MDNS_ADVERTISE=false
        fi
      else
        if confirm "Publier ce noeud en mDNS (bonjour) ?"; then
          CLUSTER_MDNS_ADVERTISE=true
        fi
      fi
    else
      CLUSTER_MDNS_SERVICE="${CLUSTER_MDNS_SERVICE:-_mascarade._tcp.local.}"
      CLUSTER_MDNS_DISCOVERY_TTL_SECONDS="${CLUSTER_MDNS_DISCOVERY_TTL_SECONDS:-60}"
      CLUSTER_MDNS_ADVERTISE="${CLUSTER_MDNS_ADVERTISE:-false}"
    fi
    CLUSTER_PEERS=$(input_optional_value "Peers cluster (peer|role|url;...)" "${CLUSTER_PEERS:-}")
  else
    NODE_ID="${NODE_ID:-node-1}"
    NODE_ROLE="${NODE_ROLE:-general}"
    NODE_LABEL="${NODE_LABEL:-Mascarade Node 1}"
    MESH_BIND_HOST=""
    MESH_SCHEME="${MESH_SCHEME:-http}"
    CLUSTER_SHARED_KEY=""
    CLUSTER_REQUEST_TIMEOUT_MS="${CLUSTER_REQUEST_TIMEOUT_MS:-5000}"
    CLUSTER_HEARTBEAT_SECONDS="${CLUSTER_HEARTBEAT_SECONDS:-30}"
    CLUSTER_FORWARD_ENABLED=false
    CLUSTER_MDNS_ENABLED="${CLUSTER_MDNS_ENABLED:-false}"
    CLUSTER_MDNS_SERVICE="${CLUSTER_MDNS_SERVICE:-_mascarade._tcp.local.}"
    CLUSTER_MDNS_DISCOVERY_TTL_SECONDS="${CLUSTER_MDNS_DISCOVERY_TTL_SECONDS:-60}"
    CLUSTER_MDNS_ADVERTISE="${CLUSTER_MDNS_ADVERTISE:-false}"
    CLUSTER_PEERS=""
  fi
}

module_core_compose() {
  echo "  core:"
  echo "    build:"
  echo "      context: ."
  echo "      dockerfile: deploy/Dockerfile.core"
  echo "    container_name: mascarade-core"
  echo "    restart: unless-stopped"
  echo "    ports:"
  echo "      - \"\${PUBLISH_BIND_HOST:-0.0.0.0}:\${CORE_PORT}:8100\""
  if [[ "${CLUSTER_ENABLED:-false}" == "true" && -n "${MESH_BIND_HOST:-}" && "${MESH_BIND_HOST}" != "${PUBLISH_BIND_HOST:-0.0.0.0}" ]]; then
    echo "      - \"\${MESH_BIND_HOST}:\${CORE_PORT}:8100\""
  fi
  echo "    env_file:"
  echo "      - .env"
  echo "    environment:"
  echo "      CORE_HOST: \${CORE_HOST}"
  echo "      CORE_PORT: \${CORE_PORT}"
  echo "      DEFAULT_PROVIDER: \${DEFAULT_PROVIDER}"
  echo "      DEFAULT_MODEL: \${DEFAULT_MODEL}"
  echo "    extra_hosts:"
  echo "      - \"host.docker.internal:host-gateway\""
  echo "    volumes:"
  echo "      - core-data:/app/data"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_core_volumes() {
  echo "  core-data:"
}
