#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/lib.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/services.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/modules/p2p_discovery.sh"

LABEL="mascarade-setup"
REFRESH_SECONDS=5

usage() {
  cat <<'EOF'
Usage: ./scripts/mascarade_setup_tui.sh [options]

Interface TUI interactive pour configurer Mascarade avec découverte P2P.

Options:
  --label NAME       Label de session (default: mascarade-setup)
  --interval N       Refresh dashboard en secondes (default: 5)
  --dashboard        Ouvre directement le dashboard live
  -h, --help         Affiche l'aide
EOF
}

die() {
  echo "mascarade-setup-tui: $*" >&2
  exit 1
}

# Fonction pour afficher un en-tête stylisé
display_header() {
  local title="$1"
  local width="${COLUMNS:-80}"
  local padding=$(((width - ${#title} - 2) / 2))
  
  echo -e "${CYAN}"
  printf '%*s' $width | tr ' ' '='
  echo
  printf '  %s%s%s  \n' "$(printf '%*s' $padding | tr ' ' ' ')" "${BOLD}${title}${NC}" "$(printf '%*s' $padding | tr ' ' ' ')"
  printf '%*s' $width | tr ' ' '='
  echo -e "${NC}"
}

# Fonction pour afficher une barre de progression
display_progress() {
  local current="$1"
  local total="$2"
  local message="$3"
  local width=40
  local percent=$((current * 100 / total))
  local filled=$((current * width / total))
  local empty=$((width - filled))
  
  echo -e "  ${CYAN}┌──────────────────────────────────────────────────────┐${NC}"
  printf "  ${CYAN}│%-40s│${NC}\n" " $message"
  printf "  ${CYAN}│${NC}"
  printf "${GREEN}%s${DIM}%s${NC}" "$(printf '%*s' $filled | tr ' ' '█')" "$(printf '%*s' $empty | tr ' ' ' ')"
  printf "${CYAN}│ %3d%% ${NC}" "$percent"
  echo -e "${CYAN}└──────────────────────────────────────────────────────┘${NC}"
}

# Fonction pour afficher un résumé visuel
display_summary_box() {
  local title="$1"
  shift
  local content=("$@")
  
  echo -e "${MAGENTA}${BOLD}  ┌──────────────────────────────────────────────────────┐${NC}"
  printf "  │ %-50s │\n" "$title"
  echo -e "  ├──────────────────────────────────────────────────────┤${NC}"
  
  for item in "${content[@]}"; do
    printf "  │ %-50s │\n" "$item"
  done
  
  echo -e "${MAGENTA}${BOLD}  └──────────────────────────────────────────────────────┘${NC}"
}

# Fonction pour afficher un menu principal amélioré
display_main_menu() {
  clear
  banner
  
  display_header "Mascarade Setup TUI"
  
  echo -e "\n${BOLD}Menu Principal:${NC}\n"
  
  echo -e "  ${GREEN}1${NC} ${BOLD}Découverte P2P${NC}"
  echo -e "     ${DIM}Découvrir automatiquement les pairs sur le réseau${NC}"
  
  echo -e "  ${GREEN}2${NC} ${BOLD}Sélection automatique des services${NC}"
  echo -e "     ${DIM}Configurer les services basée sur les pairs découverts${NC}"
  
  echo -e "  ${GREEN}3${NC} ${BOLD}Configuration manuelle${NC}"
  echo -e "     ${DIM}Configurer manuellement les services et paramètres${NC}"
  
  echo -e "  ${GREEN}4${NC} ${BOLD}Afficher la configuration actuelle${NC}"
  echo -e "     ${DIM}Voir la configuration actuelle et les pairs${NC}"
  
  echo -e "  ${RED}5${NC} ${BOLD}Quitter${NC}"
  
  echo -e "\n${DIM}Utilisez les flèches et Entrée pour sélectionner${NC}\n"
}

# Fonction pour afficher un menu de découverte P2P amélioré
display_p2p_menu() {
  clear
  banner
  
  display_header "Découverte P2P"
  
  echo -e "\n${BOLD}Choisissez une méthode de découverte:${NC}\n"
  
  echo -e "  ${GREEN}1${NC} ${BOLD}mDNS (recommandé)${NC}"
  echo -e "     ${DIM}Utilise avahi-browse ou dns-sd pour la découverte${NC}"
  
  echo -e "  ${GREEN}2${NC} ${BOLD}Broadcast UDP${NC}"
  echo -e "     ${DIM}Utilise la diffusion broadcast UDP${NC}"
  
  echo -e "  ${GREEN}3${NC} ${BOLD}Manuel${NC}"
  echo -e "     ${DIM}Aucune découverte automatique${NC}"
  
  echo -e "  ${YELLOW}4${NC} ${BOLD}Retour${NC}"
  
  echo -e "\n${DIM}Méthode actuelle: ${DISCOVERY_METHOD:-Aucune}${NC}\n"
}

main() {
  local direct_dashboard=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --label)
        [[ $# -ge 2 ]] || die "--label requires a value"
        LABEL="$2"
        shift 2
        ;;
      --interval)
        [[ $# -ge 2 ]] || die "--interval requires a value"
        [[ "$2" =~ ^[0-9]+$ ]] || die "--interval must be a non-negative integer"
        REFRESH_SECONDS="$2"
        shift 2
        ;;
      --dashboard)
        direct_dashboard=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown option: $1"
        ;;
    esac
  done
  if [[ ! -t 0 || ! -t 1 ]]; then
    echo "mascarade-setup-tui: interactive TTY required" >&2
    exit 1
  fi
  activate_tui

  if [[ "$direct_dashboard" -eq 1 ]]; then
    live_dashboard
  fi

  while true; do
    display_main_menu
    
    echo -ne "  ${YELLOW}?${NC} Choix ${DIM}[1-5]${NC} " >&2
    read -r choice || true
    choice=${choice:-1}
    
    case "$choice" in
      1) p2p_discovery_menu ;;
      2) auto_select_services ;;
      3) manual_configuration ;;
      4) show_current_config ;;
      5) exit 0 ;;
      *) warn "Choix invalide, veuillez réessayer"; sleep 1 ;;
    esac
  done
}

p2p_discovery_menu() {
  while true; do
    display_p2p_menu
    
    echo -ne "  ${YELLOW}?${NC} Choix ${DIM}[1-4]${NC} " >&2
    read -r choice || true
    choice=${choice:-1}
    
    case "$choice" in
      1)
        DISCOVERY_METHOD="mdns"
        clear
        banner
        display_header "Découverte P2P - mDNS"
        echo ""
        module_p2p_discovery
        break
        ;;
      2)
        DISCOVERY_METHOD="broadcast"
        clear
        banner
        display_header "Découverte P2P - Broadcast UDP"
        echo ""
        module_p2p_discovery
        break
        ;;
      3)
        DISCOVERY_METHOD="manual"
        clear
        banner
        display_header "Mode Manuel"
        echo ""
        info "Mode manuel sélectionné - aucune découverte automatique"
        break
        ;;
      4)
        return 0
        ;;
      *)
        warn "Choix invalide, veuillez réessayer"
        sleep 1
        ;;
    esac
  done
  
  echo ""
  echo -ne "  ${YELLOW}?${NC} Appuyez sur Entrée pour continuer... " >&2
  read -r || true
}

auto_select_services() {
  clear
  banner
  display_header "Sélection Automatique des Services"
  
  if [[ -z "${CLUSTER_PEERS:-}" ]]; then
    echo ""
    display_progress 0 1 "Vérification des pairs configurés"
    warn "Aucun pair P2P configuré. Veuillez d'abord effectuer une découverte P2P."
    echo ""
    echo -ne "  ${YELLOW}?${NC} Appuyez sur Entrée pour continuer... " >&2
    read -r || true
    return 0
  fi

  echo ""
  display_progress 1 3 "Analyse des pairs configurés"
  info "Analyse des pairs configurés..."
  
  display_progress 2 3 "Sélection automatique des services"
  auto_select_services_based_on_peers
  
  display_progress 3 3 "Finalisation"
  echo ""
  
  display_header "Services Sélectionnés"
  echo ""
  show_service_selection_summary
  
  echo ""
  if confirm "Voulez-vous ajuster cette sélection manuellement ?"; then
    checkbox_select_ids
    echo ""
    display_header "Services Mis à Jour"
    echo ""
    show_service_selection_summary
  fi
  
  echo ""
  ok "Sélection des services terminée avec succès !"
  echo ""
  echo -ne "  ${YELLOW}?${NC} Appuyez sur Entrée pour continuer... " >&2
  read -r || true
}

manual_configuration() {
  clear
  banner
  display_header "Configuration Manuelle"
  echo ""
  
  display_progress 1 2 "Lancement du wizard de configuration"
  service_selection_wizard
  
  display_progress 2 2 "Finalisation"
  echo ""
  display_header "Configuration Complétée"
  echo ""
  show_service_selection_summary
  
  echo ""
  ok "Configuration manuelle terminée avec succès !"
  echo ""
  echo -ne "  ${YELLOW}?${NC} Appuyez sur Entrée pour continuer... " >&2
  read -r || true
}

show_current_config() {
  clear
  banner
  display_header "Configuration Actuelle"
  
  # Afficher la configuration P2P
  echo ""
  display_summary_box "Paramètres de Découverte P2P" \
    "Méthode: ${DISCOVERY_METHOD:-mdns}" \
    "Timeout: ${DISCOVERY_TIMEOUT:-5} secondes"
  
  # Afficher la configuration cluster
  echo ""
  if [[ "${CLUSTER_ENABLED:-false}" == "true" ]]; then
    display_summary_box "Configuration Cluster" \
      "Mode: Activé" \
      "Node ID: ${NODE_ID:-node-1}" \
      "Role: ${NODE_ROLE:-general}" \
      "Label: ${NODE_LABEL:-Mascarade Node 1}"
    
    # Afficher les pairs configurés
    if [[ -n "${CLUSTER_PEERS:-}" ]]; then
      echo ""
      echo -e "  ${BOLD}${MAGENTA}Pairs Configurés:${NC}"
      echo -e "  ${CYAN}──────────────────────────────────────────────────────${NC}"
      IFS=';' read -ra peer_list <<< "${CLUSTER_PEERS:-}"
      for peer_entry in "${peer_list[@]}"; do
        IFS='|' read -ra peer_parts <<< "$peer_entry"
        if [[ ${#peer_parts[@]} -eq 3 ]]; then
          printf "  ${GREEN}✓ ${NC}${BOLD}%-20s${NC}  ${DIM}%-10s${NC}  ${CYAN}%s${NC}\n" \
            "${peer_parts[0]}" "(${peer_parts[1]})" "${peer_parts[2]}"
        fi
      done
      echo -e "  ${CYAN}──────────────────────────────────────────────────────${NC}"
    else
      echo ""
      warn "Aucun pair configuré"
    fi
  else
    echo ""
    display_summary_box "Configuration Cluster" "Mode: Désactivé"
  fi
  
  # Afficher les services sélectionnés
  echo ""
  display_header "Services Sélectionnés"
  echo ""
  show_service_selection_summary
  
  echo ""
  echo -ne "  ${YELLOW}?${NC} Appuyez sur Entrée pour continuer... " >&2
  read -r || true
}

live_dashboard() {
  section "Live Dashboard"
  info "Fonctionnalité à implémenter"
}

# Initialisation
DISCOVERY_METHOD="${DISCOVERY_METHOD:-mdns}"
DISCOVERY_TIMEOUT="${DISCOVERY_TIMEOUT:-5}"
CLUSTER_ENABLED="${CLUSTER_ENABLED:-false}"
NODE_ID="${NODE_ID:-node-1}"
NODE_ROLE="${NODE_ROLE:-general}"
NODE_LABEL="${NODE_LABEL:-Mascarade Node 1}"
CLUSTER_PEERS="${CLUSTER_PEERS:-}"

main "$@"
