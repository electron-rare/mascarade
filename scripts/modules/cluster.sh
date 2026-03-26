#!/usr/bin/env bash
# scripts/modules/cluster.sh — Module Réseau P2P

module_cluster_config() {
  CLUSTER_ENABLED=true

  NODE_ID=$(input_value "Node ID P2P" "${NODE_ID:-node-1}")
  NODE_ROLE=$(input_value "Rôle du noeud P2P" "${NODE_ROLE:-general}")
  NODE_LABEL=$(input_value "Label du noeud" "${NODE_LABEL:-Mascarade Node 1}")
  MESH_BIND_HOST=$(input_value "IP/VPN du noeud (bind mesh)" "${MESH_BIND_HOST:-}")
  MESH_SCHEME=$(input_value "Schéma mesh (http/https)" "${MESH_SCHEME:-http}")
  CLUSTER_SHARED_KEY=$(input_optional_secret "Clé Bearer inter-noeuds" "${CLUSTER_SHARED_KEY:-}")
  CLUSTER_REQUEST_TIMEOUT_MS=$(input_value "Timeout P2P (ms)" "${CLUSTER_REQUEST_TIMEOUT_MS:-5000}")
  CLUSTER_HEARTBEAT_SECONDS=$(input_value "Heartbeat logique peers (s)" "${CLUSTER_HEARTBEAT_SECONDS:-30}")

  if [[ "${CLUSTER_FORWARD_ENABLED:-false}" == "true" ]]; then
    if ! confirm "Maintenir le relay core->core ?"; then
      CLUSTER_FORWARD_ENABLED=false
    fi
  else
    if confirm "Activer le relay core->core ?"; then
      CLUSTER_FORWARD_ENABLED=true
    else
      CLUSTER_FORWARD_ENABLED=false
    fi
  fi

  CLUSTER_PEERS=$(input_optional_value "Peers (peer|role|url;...)" "${CLUSTER_PEERS:-}")
}

module_cluster_compose() {
  :
}

module_cluster_volumes() {
  :
}
