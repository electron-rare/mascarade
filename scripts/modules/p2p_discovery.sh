#!/usr/bin/env bash
# scripts/modules/p2p_discovery.sh — Découverte de pairs P2P pour Mascarade

# Fonction pour découvrir les pairs P2P sur le réseau local
module_p2p_discovery() {
    local discovery_method="${DISCOVERY_METHOD:-mdns}"
    local discovery_timeout="${DISCOVERY_TIMEOUT:-5}"
    local discovered_peers=""

    echo ""
    echo -e "  ${BOLD}Découverte de pairs P2P${NC}"
    info "Méthode de découverte : $discovery_method"
    info "Timeout : $discovery_timeout secondes"

    case "$discovery_method" in
        mdns)
            if command -v avahi-browse &>/dev/null; then
                info "Utilisation d'avahi-browse pour la découverte mDNS..."
                discovered_peers=$(avahi-browse -at --timeout="$discovery_timeout" --resolve | grep "_mascarade._tcp" | awk '{print $8}' | sort -u)
            elif command -v dns-sd &>/dev/null; then
                info "Utilisation de dns-sd pour la découverte mDNS..."
                discovered_peers=$(dns-sd -B _mascarade._tcp local --timeout "$discovery_timeout" 2>/dev/null | grep "Add" | awk '{print $6}' | sed 's/\.$//')
            else
                warn "Aucun outil de découverte mDNS disponible (avahi-browse ou dns-sd)"
                return 1
            fi
            ;;
        broadcast)
            info "Utilisation de la diffusion broadcast UDP..."
            discovered_peers=$(timeout "$discovery_timeout" bash -c 'echo "MASCARADE_DISCOVERY" | nc -u -b -w1 255.255.255.255 12345 2>/dev/null' || true)
            ;;
        manual)
            info "Mode manuel - aucun pair découvert automatiquement"
            discovered_peers=""
            ;;
        *)
            warn "Méthode de découverte inconnue : $discovery_method"
            return 1
            ;;
    esac

    if [[ -z "$discovered_peers" ]]; then
        info "Aucun pair P2P découvert"
        return 0
    fi

    echo ""
    echo -e "  ${BOLD}Pairs P2P découverts :${NC}"
    local peer_count=0
    while IFS= read -r peer; do
        if [[ -n "$peer" ]]; then
            echo -e "    ${GREEN}✓${NC} $peer"
            ((peer_count++))
        fi
    done <<< "$discovered_peers"

    echo ""
    info "Nombre de pairs découverts : $peer_count"

    if [[ $peer_count -gt 0 ]]; then
        if confirm "Voulez-vous ajouter ces pairs à votre configuration cluster ?"; then
            local peers_config=""
            while IFS= read -r peer; do
                if [[ -n "$peer" ]]; then
                    local peer_id="peer-$peer_count"
                    local role="general"
                    if [[ "$peer" == *"gpu"* ]]; then
                        role="gpu"
                    elif [[ "$peer" == *"edge"* ]]; then
                        role="edge"
                    fi
                    peers_config+="$peer_id|$role|http://$peer:8100;"
                    ((peer_count--))
                fi
            done <<< "$discovered_peers"

            if [[ -n "$peers_config" ]]; then
                CLUSTER_PEERS="$peers_config"
                ok "Configuration des pairs mise à jour"
                info "CLUSTER_PEERS=$CLUSTER_PEERS"
            fi
        fi
    fi

    return 0
}

# Fonction pour configurer la méthode de découverte
module_p2p_discovery_config() {
    DISCOVERY_METHOD=$(input_value "Méthode de découverte P2P" "${DISCOVERY_METHOD:-mdns}")
    DISCOVERY_TIMEOUT=$(input_value "Timeout de découverte (secondes)" "${DISCOVERY_TIMEOUT:-5}")

    if [[ "$DISCOVERY_METHOD" == "broadcast" ]]; then
        BROADCAST_PORT=$(input_value "Port de diffusion UDP" "${BROADCAST_PORT:-12345}")
    fi
}

# Fonction pour générer la configuration docker-compose pour la découverte P2P
module_p2p_discovery_compose() {
    echo "  # P2P Discovery (intégré au core)"
}

# Fonction pour générer les volumes pour la découverte P2P
module_p2p_discovery_volumes() {
    echo ""
}

# Export des variables pour les autres scripts
export DISCOVERY_METHOD
