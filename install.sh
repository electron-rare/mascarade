#!/usr/bin/env bash
# install.sh — Installation TUI de Mascarade
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# ══════════════════════════════════════════════
# Couleurs & helpers
# ══════════════════════════════════════════════
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m'

TERM_WIDTH=$(tput cols 2>/dev/null || echo 80)

line()    { printf '%*s\n' "$TERM_WIDTH" '' | tr ' ' '─'; }
log()     { echo -e "  ${CYAN}▸${NC} $*"; }
ok()      { echo -e "  ${GREEN}✓${NC} $*"; }
warn()    { echo -e "  ${YELLOW}!${NC} $*"; }
err()     { echo -e "  ${RED}✗${NC} $*"; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}$1${NC}"; line; }

banner() {
    clear
    echo -e "${MAGENTA}${BOLD}"
    cat << 'ART'
    ╔╦╗╔═╗╔═╗╔═╗╔═╗╦═╗╔═╗╔╦╗╔═╗
    ║║║╠═╣╚═╗║  ╠═╣╠╦╝╠═╣ ║║║╣
    ╩ ╩╩ ╩╚═╝╚═╝╩ ╩╩╚═╩ ╩═╩╝╚═╝
ART
    echo -e "${NC}${DIM}    Orchestration LLM multi-providers${NC}"
    echo ""
    line
}

confirm() {
    local msg="$1"
    echo -ne "  ${YELLOW}?${NC} ${msg} ${DIM}[O/n]${NC} "
    read -r answer
    [[ -z "$answer" || "$answer" =~ ^[OoYy] ]]
}

input_secret() {
    local prompt="$1" default="${2:-}"
    if [[ -n "$default" && "$default" != sk-ant-... && "$default" != sk-... && "$default" != ... && "$default" != ntn_... ]]; then
        local masked="${default:0:8}...${default: -4}"
        echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[${masked}]${NC} " >&2
    else
        echo -ne "  ${YELLOW}?${NC} ${prompt} " >&2
    fi
    read -r value
    if [[ -z "$value" ]]; then
        echo "$default"
    else
        echo "$value"
    fi
}

input_value() {
    local prompt="$1" default="${2:-}"
    echo -ne "  ${YELLOW}?${NC} ${prompt} ${DIM}[${default}]${NC} " >&2
    read -r value
    echo "${value:-$default}"
}

# ══════════════════════════════════════════════
# Menu single-select (↑/↓ + Entrée)
# ══════════════════════════════════════════════
menu_select() {
    local title="$1"; shift
    local options=("$@")
    local selected=0
    local count=${#options[@]}

    tput civis 2>/dev/null || true
    trap 'tput cnorm 2>/dev/null || true' RETURN

    while true; do
        echo -e "\n  ${BOLD}$title${NC}\n"
        for i in "${!options[@]}"; do
            if [[ $i -eq $selected ]]; then
                echo -e "  ${CYAN}${BOLD} ▶ ${options[$i]} ${NC}"
            else
                echo -e "  ${DIM}   ${options[$i]}${NC}"
            fi
        done
        echo -e "\n  ${DIM}↑/↓ naviguer, Entrée valider${NC}"

        read -rsn1 key
        case "$key" in
            A) ((selected > 0)) && ((selected--)) ;;
            B) ((selected < count - 1)) && ((selected++)) ;;
            '') break ;;
        esac

        tput cuu $((count + 4)) 2>/dev/null
        for ((i = 0; i < count + 4; i++)); do
            tput el 2>/dev/null; tput cud1 2>/dev/null
        done
        tput cuu $((count + 4)) 2>/dev/null
    done

    tput cnorm 2>/dev/null || true
    return $selected
}

# ══════════════════════════════════════════════
# Checkbox multi-select (↑/↓ + Espace + Entrée)
# ══════════════════════════════════════════════

# Déclaration des services
# Format: ID|Label|Description|Port|Catégorie|Activé par défaut (1/0)
declare -a SVC_IDS=()
declare -A SVC_LABEL=()
declare -A SVC_DESC=()
declare -A SVC_PORT=()
declare -A SVC_CAT=()
declare -A SVC_ON=()

define_service() {
    local id="$1" label="$2" desc="$3" port="$4" cat="$5" on="${6:-0}"
    SVC_IDS+=("$id")
    SVC_LABEL[$id]="$label"
    SVC_DESC[$id]="$desc"
    SVC_PORT[$id]="$port"
    SVC_CAT[$id]="$cat"
    SVC_ON[$id]="$on"
}

# ── Mascarade ──
define_service "core"       "Mascarade Core"    "FastAPI — routeur LLM, agents, orchestrateur"   "8100" "mascarade" 1
define_service "api"        "Mascarade API"     "Hono — gateway HTTP, auth middleware"            "3000" "mascarade" 1

# ── Outils ──
define_service "litellm"    "LiteLLM"           "Proxy LLM unifié + cache Redis"                 "4000" "tools" 0
define_service "n8n"        "n8n"               "Automatisation workflows low-code"               "5678" "tools" 0
define_service "langfuse"   "Langfuse"          "Observabilité LLM (tracing, evals)"             "3200" "tools" 0
define_service "dify"       "Dify"              "App builder IA (API + Web + Worker)"             "3500" "tools" 0
define_service "clickhouse" "ClickHouse"        "Base analytique colonnaire (requis par Langfuse)" "—"   "tools" 0

# ── Infra ──
define_service "ollama"     "Ollama"            "Serveur LLM local (llama, mistral, etc.)"       "11434" "infra" 0
define_service "open-webui" "Open WebUI"        "Interface chat pour Ollama"                      "3000"  "infra" 0
define_service "redis"      "Redis"             "Cache & broker (requis par LiteLLM, Firecrawl)"  "6379"  "infra" 0
define_service "postgres"   "PostgreSQL"        "Base relationnelle (Langfuse, Dify, n8n)"        "5432"  "infra" 0
define_service "qdrant"     "Qdrant"            "Base vectorielle (embeddings, RAG)"              "6333"  "infra" 0
define_service "grafana"    "Grafana"           "Dashboards monitoring"                           "3001"  "infra" 0
define_service "prometheus" "Prometheus"        "Collecte métriques"                              "9090"  "infra" 0

checkbox_select() {
    local current_cat=""
    local cursor=0
    local count=${#SVC_IDS[@]}

    tput civis 2>/dev/null || true

    while true; do
        echo -e "\n  ${BOLD}Sélection des services à déployer${NC}\n"

        current_cat=""
        local display_idx=0
        for i in "${!SVC_IDS[@]}"; do
            local id="${SVC_IDS[$i]}"
            local cat="${SVC_CAT[$id]}"

            # En-tête de catégorie
            if [[ "$cat" != "$current_cat" ]]; then
                current_cat="$cat"
                case "$cat" in
                    mascarade) echo -e "  ${MAGENTA}${BOLD}MASCARADE${NC}" ;;
                    tools)     echo -e "  ${CYAN}${BOLD}OUTILS${NC}" ;;
                    infra)     echo -e "  ${YELLOW}${BOLD}INFRASTRUCTURE${NC}" ;;
                esac
            fi

            # Checkbox
            local check=" "
            [[ "${SVC_ON[$id]}" == "1" ]] && check="${GREEN}✓${NC}"

            local port_info=""
            [[ "${SVC_PORT[$id]}" != "—" ]] && port_info="${DIM}:${SVC_PORT[$id]}${NC}"

            if [[ $i -eq $cursor ]]; then
                echo -e "  ${WHITE}${BOLD} ▶ [${check}${WHITE}${BOLD}] ${SVC_LABEL[$id]}${NC} ${port_info}  ${DIM}${SVC_DESC[$id]}${NC}"
            else
                echo -e "  ${DIM}   [${check}${DIM}] ${SVC_LABEL[$id]}${NC} ${port_info}  ${DIM}${SVC_DESC[$id]}${NC}"
            fi
        done

        # Compteur sélection
        local sel_count=0
        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" == "1" ]] && ((sel_count++))
        done
        echo ""
        echo -e "  ${DIM}↑/↓ naviguer  ␣ (dé)cocher  a tout  n rien  Entrée valider${NC}"
        echo -e "  ${DIM}${sel_count} service(s) sélectionné(s)${NC}"

        read -rsn1 key
        case "$key" in
            A) ((cursor > 0)) && ((cursor--)) ;;
            B) ((cursor < count - 1)) && ((cursor++)) ;;
            ' ')
                local id="${SVC_IDS[$cursor]}"
                if [[ "${SVC_ON[$id]}" == "1" ]]; then
                    SVC_ON[$id]="0"
                else
                    SVC_ON[$id]="1"
                fi
                ;;
            a|A)
                for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="1"; done
                ;;
            n|N)
                for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="0"; done
                ;;
            '') break ;;
        esac

        # Calculer nombre de lignes affichées pour redessiner
        # Titre(2) + 3 headers + items + 3 footer
        local total_lines=$((count + 8))
        tput cuu "$total_lines" 2>/dev/null
        for ((i = 0; i < total_lines; i++)); do
            tput el 2>/dev/null; tput cud1 2>/dev/null
        done
        tput cuu "$total_lines" 2>/dev/null
    done

    tput cnorm 2>/dev/null || true
}

# Vérifie si un service est sélectionné
svc_selected() { [[ "${SVC_ON[$1]:-0}" == "1" ]]; }

# Liste des services sélectionnés pour une catégorie
selected_in_cat() {
    local cat="$1"
    for id in "${SVC_IDS[@]}"; do
        [[ "${SVC_CAT[$id]}" == "$cat" && "${SVC_ON[$id]}" == "1" ]] && echo "$id"
    done
}

# ══════════════════════════════════════════════
# Installation automatique des prérequis
# ══════════════════════════════════════════════

# Détecte le gestionnaire de paquets
detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v yum &>/dev/null; then
        echo "yum"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    else
        echo ""
    fi
}

# Vérifie si on peut utiliser sudo
ensure_sudo() {
    if [[ $EUID -eq 0 ]]; then
        echo ""
        return 0
    fi
    if command -v sudo &>/dev/null; then
        echo "sudo"
        return 0
    fi
    err "sudo non disponible et pas root — installation impossible"
    return 1
}

install_docker() {
    local sudo_cmd
    sudo_cmd=$(ensure_sudo) || return 1
    local pkg_mgr
    pkg_mgr=$(detect_pkg_manager)

    log "Installation de Docker Engine + Compose..."

    case "$pkg_mgr" in
        apt)
            log "Ajout du repo Docker officiel..."
            $sudo_cmd apt-get update -qq
            $sudo_cmd apt-get install -y -qq ca-certificates curl gnupg >/dev/null 2>&1

            $sudo_cmd install -m 0755 -d /etc/apt/keyrings
            if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
                curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $sudo_cmd tee /etc/apt/keyrings/docker.asc > /dev/null
                $sudo_cmd chmod a+r /etc/apt/keyrings/docker.asc
            fi

            local codename
            codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" | \
                $sudo_cmd tee /etc/apt/sources.list.d/docker.list > /dev/null

            $sudo_cmd apt-get update -qq
            $sudo_cmd apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1
            ;;
        dnf|yum)
            $sudo_cmd "$pkg_mgr" install -y -q dnf-plugins-core 2>/dev/null || true
            $sudo_cmd "$pkg_mgr" config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo 2>/dev/null || \
                $sudo_cmd "$pkg_mgr" config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null
            $sudo_cmd "$pkg_mgr" install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        pacman)
            $sudo_cmd pacman -S --noconfirm docker docker-compose
            ;;
        *)
            err "Gestionnaire de paquets non supporté pour l'installation auto de Docker"
            echo -e "  ${DIM}Installe manuellement : https://docs.docker.com/engine/install/${NC}"
            return 1
            ;;
    esac

    # Démarrer le service
    $sudo_cmd systemctl start docker 2>/dev/null || true
    $sudo_cmd systemctl enable docker 2>/dev/null || true

    # Ajouter l'utilisateur au groupe docker
    if [[ $EUID -ne 0 ]]; then
        $sudo_cmd usermod -aG docker "$USER" 2>/dev/null || true
        warn "Ajouté au groupe docker — un 'newgrp docker' ou re-login peut être nécessaire"
    fi

    if command -v docker &>/dev/null; then
        ok "Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1) installé"
        return 0
    else
        err "L'installation de Docker semble avoir échoué"
        return 1
    fi
}

install_node22() {
    local sudo_cmd
    sudo_cmd=$(ensure_sudo) || return 1

    log "Installation de Node.js 22 LTS..."

    # Méthode 1 : fnm (recommandé, pas besoin de sudo pour le runtime)
    if command -v fnm &>/dev/null; then
        log "Utilisation de fnm..."
        fnm install 22
        fnm use 22
        fnm default 22
        ok "Node.js $(node -v) installé via fnm"
        return 0
    fi

    # Méthode 2 : nvm
    if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
        log "Utilisation de nvm..."
        # shellcheck disable=SC1091
        source "$HOME/.nvm/nvm.sh"
        nvm install 22
        nvm use 22
        nvm alias default 22
        ok "Node.js $(node -v) installé via nvm"
        return 0
    fi

    # Méthode 3 : NodeSource repo (apt)
    local pkg_mgr
    pkg_mgr=$(detect_pkg_manager)

    case "$pkg_mgr" in
        apt)
            log "Installation via le repo NodeSource..."
            curl -fsSL https://deb.nodesource.com/setup_22.x | $sudo_cmd bash - >/dev/null 2>&1
            $sudo_cmd apt-get install -y -qq nodejs >/dev/null 2>&1
            ;;
        dnf|yum)
            curl -fsSL https://rpm.nodesource.com/setup_22.x | $sudo_cmd bash - >/dev/null 2>&1
            $sudo_cmd "$pkg_mgr" install -y -q nodejs
            ;;
        pacman)
            $sudo_cmd pacman -S --noconfirm nodejs npm
            ;;
        *)
            # Fallback : installer nvm puis node
            log "Installation de nvm + Node.js 22..."
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
            export NVM_DIR="$HOME/.nvm"
            # shellcheck disable=SC1091
            [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
            nvm install 22
            nvm use 22
            nvm alias default 22
            ;;
    esac

    if command -v node &>/dev/null; then
        local ver
        ver=$(node -v)
        local major=${ver#v}
        major=${major%%.*}
        if [[ $major -ge 22 ]]; then
            ok "Node.js $ver installé"
            return 0
        else
            warn "Node.js installé mais version $ver (attendu 22+)"
            return 1
        fi
    else
        err "L'installation de Node.js semble avoir échoué"
        return 1
    fi
}

# ══════════════════════════════════════════════
# Vérification des prérequis (adaptée à la sélection)
# ══════════════════════════════════════════════
check_prerequisites() {
    local missing_docker=false
    local missing_node=false
    local node_outdated=false

    # Python — requis si core sélectionné (dev local)
    if svc_selected "core"; then
        if command -v python3 &>/dev/null; then
            local pyver
            pyver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            if python3 -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
                ok "Python $pyver"
            else
                warn "Python 3.11+ recommandé pour dev local (trouvé $pyver)"
            fi
        else
            warn "Python 3 non trouvé (optionnel si déploiement Docker uniquement)"
        fi
    fi

    # Node — requis si api sélectionné
    if svc_selected "api"; then
        if command -v node &>/dev/null; then
            local nodever
            nodever=$(node -v)
            local nodemajor=${nodever#v}
            nodemajor=${nodemajor%%.*}
            if [[ $nodemajor -ge 22 ]]; then
                ok "Node.js $nodever"
            else
                warn "Node.js $nodever détecté — le projet requiert v22+"
                node_outdated=true
            fi
        else
            warn "Node.js non trouvé"
            missing_node=true
        fi
    fi

    # npm
    if command -v npm &>/dev/null; then
        ok "npm $(npm -v)"
    elif svc_selected "api"; then
        warn "npm non trouvé (sera installé avec Node.js)"
    fi

    # Docker — requis dès qu'on sélectionne un container
    if command -v docker &>/dev/null; then
        ok "Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)"
        if docker compose version &>/dev/null; then
            ok "Docker Compose $(docker compose version --short 2>/dev/null)"
        else
            warn "Plugin Docker Compose manquant"
            missing_docker=true
        fi
    else
        missing_docker=true
    fi

    # curl
    if command -v curl &>/dev/null; then
        ok "curl $(curl --version 2>/dev/null | head -1 | grep -oP '\d+\.\d+\.\d+' | head -1)"
    else
        warn "curl non trouvé (nécessaire pour les health checks)"
    fi

    # Git
    if command -v git &>/dev/null; then
        ok "Git $(git --version | awk '{print $3}')"
    fi

    # ── Proposer l'installation automatique ──
    local need_install=false

    if [[ "$missing_docker" == true ]]; then
        echo ""
        echo -e "  ${YELLOW}${BOLD}Docker n'est pas installé.${NC}"
        echo -e "  ${DIM}Docker est nécessaire pour déployer les services.${NC}"
        if confirm "Installer Docker Engine + Compose automatiquement ?"; then
            install_docker || true
            need_install=true
        else
            warn "Docker non installé — le déploiement Docker ne fonctionnera pas"
        fi
    fi

    if [[ "$missing_node" == true || "$node_outdated" == true ]]; then
        echo ""
        if [[ "$missing_node" == true ]]; then
            echo -e "  ${YELLOW}${BOLD}Node.js n'est pas installé.${NC}"
        else
            echo -e "  ${YELLOW}${BOLD}Node.js est trop ancien (v18, requis v22+).${NC}"
        fi
        echo -e "  ${DIM}Node.js 22+ est nécessaire pour l'API Hono et le dev local.${NC}"

        menu_select "Comment installer Node.js 22 ?" \
            "Installer via NodeSource (apt, recommandé)" \
            "Installer via nvm (multi-versions)" \
            "Ne pas installer (je gère moi-même)"
        local node_choice=$?

        case $node_choice in
            0)
                install_node22
                need_install=true
                ;;
            1)
                log "Installation de nvm..."
                if [[ ! -s "$HOME/.nvm/nvm.sh" ]]; then
                    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash 2>&1 | tail -3
                    export NVM_DIR="$HOME/.nvm"
                    # shellcheck disable=SC1091
                    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
                fi
                # shellcheck disable=SC1091
                [ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh"
                nvm install 22 2>&1 | tail -3
                nvm use 22
                nvm alias default 22
                if command -v node &>/dev/null; then
                    ok "Node.js $(node -v) installé via nvm"
                fi
                need_install=true
                ;;
            2)
                warn "Node.js 22 non installé — certaines fonctionnalités peuvent ne pas marcher"
                ;;
        esac
    fi

    # Vérification post-installation
    if [[ "$need_install" == true ]]; then
        echo ""
        log "Vérification post-installation..."
        command -v docker &>/dev/null && ok "Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)"
        command -v node &>/dev/null   && ok "Node.js $(node -v)"
        command -v npm &>/dev/null    && ok "npm $(npm -v)"
    fi
}

# ══════════════════════════════════════════════
# Configuration .env (adaptée aux services sélectionnés)
# ══════════════════════════════════════════════
configure_env() {
    local env_file="$REPO_DIR/.env"

    # Charger les valeurs existantes
    local ANTHROPIC_API_KEY="" OPENAI_API_KEY="" MISTRAL_API_KEY="" NOTION_API_KEY=""
    local MASCARADE_API_KEY="" CORE_PORT="8100" API_PORT="3000"
    local DEFAULT_PROVIDER="claude" DEFAULT_MODEL="claude-sonnet-4-6"
    local LITELLM_PORT="4000" N8N_PORT="5678" LANGFUSE_PORT="3200"
    local DIFY_API_PORT="5001" DIFY_WEB_PORT="3500"
    local OLLAMA_PORT="11434" OPEN_WEBUI_PORT="3000"
    local REDIS_PORT="6379" POSTGRES_PORT="5432" POSTGRES_PASSWORD="changeme"
    local QDRANT_PORT="6333" GRAFANA_PORT="3001" PROMETHEUS_PORT="9090"
    local CLICKHOUSE_PORT="9000"
    local LANGFUSE_SECRET_KEY="" LANGFUSE_NEXT_PUBLIC_KEY="" ENCRYPTION_KEY=""

    if [[ -f "$env_file" ]]; then
        # shellcheck disable=SC1090
        source <(grep -E '^[A-Z_]+=.' "$env_file" 2>/dev/null || true)
        ok "Fichier .env existant chargé"
    fi

    # ── Clés API LLM ──
    if svc_selected "core" || svc_selected "litellm"; then
        echo ""
        echo -e "  ${BOLD}Clés API LLM${NC} ${DIM}(laisser vide pour désactiver le provider)${NC}"
        echo ""
        ANTHROPIC_API_KEY=$(input_secret "Anthropic API Key :" "$ANTHROPIC_API_KEY")
        OPENAI_API_KEY=$(input_secret "OpenAI API Key :" "$OPENAI_API_KEY")
        MISTRAL_API_KEY=$(input_secret "Mistral API Key :" "$MISTRAL_API_KEY")
    fi

    # ── Notion ──
    if svc_selected "core"; then
        echo ""
        echo -e "  ${BOLD}Intégrations Core${NC}"
        echo ""
        NOTION_API_KEY=$(input_secret "Notion API Key (optionnel) :" "$NOTION_API_KEY")
    fi

    # ── Auth Mascarade ──
    if svc_selected "api"; then
        echo ""
        echo -e "  ${BOLD}Authentification Mascarade${NC}"
        echo ""
        if [[ -z "$MASCARADE_API_KEY" ]]; then
            if confirm "Générer un token Bearer API ?"; then
                MASCARADE_API_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n')
                ok "Token généré : ${MASCARADE_API_KEY:0:12}..."
            fi
        else
            if confirm "Garder le token existant ?"; then
                ok "Token conservé"
            else
                MASCARADE_API_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n')
                ok "Nouveau token : ${MASCARADE_API_KEY:0:12}..."
            fi
        fi
    fi

    # ── Ports Mascarade ──
    if svc_selected "core" || svc_selected "api"; then
        echo ""
        echo -e "  ${BOLD}Ports Mascarade${NC}"
        echo ""
        svc_selected "core" && CORE_PORT=$(input_value "Port Core (FastAPI) :" "$CORE_PORT")
        svc_selected "api"  && API_PORT=$(input_value "Port API (Hono) :" "$API_PORT")
    fi

    # ── Provider par défaut ──
    if svc_selected "core"; then
        echo ""
        echo -e "  ${BOLD}Provider par défaut${NC}"
        echo ""
        DEFAULT_PROVIDER=$(input_value "Provider (claude/openai/mistral) :" "$DEFAULT_PROVIDER")
        DEFAULT_MODEL=$(input_value "Modèle :" "$DEFAULT_MODEL")
    fi

    # ── Langfuse config ──
    if svc_selected "langfuse"; then
        echo ""
        echo -e "  ${BOLD}Configuration Langfuse${NC}"
        echo ""
        LANGFUSE_PORT=$(input_value "Port Langfuse :" "$LANGFUSE_PORT")
        if [[ -z "$LANGFUSE_SECRET_KEY" ]]; then
            LANGFUSE_SECRET_KEY="sk-lf-$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
            ok "Secret key Langfuse générée"
        fi
        if [[ -z "$LANGFUSE_NEXT_PUBLIC_KEY" ]]; then
            LANGFUSE_NEXT_PUBLIC_KEY="pk-lf-$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
            ok "Public key Langfuse générée"
        fi
        if [[ -z "$ENCRYPTION_KEY" ]]; then
            ENCRYPTION_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n')
            ok "Encryption key générée"
        fi
    fi

    # ── Ports outils ──
    local tools_selected=false
    for id in $(selected_in_cat "tools"); do
        tools_selected=true; break
    done

    if [[ "$tools_selected" == true ]]; then
        echo ""
        echo -e "  ${BOLD}Ports Outils${NC}"
        echo ""
        svc_selected "litellm"    && LITELLM_PORT=$(input_value "Port LiteLLM :" "$LITELLM_PORT")
        svc_selected "n8n"        && N8N_PORT=$(input_value "Port n8n :" "$N8N_PORT")
        svc_selected "dify"       && DIFY_WEB_PORT=$(input_value "Port Dify Web :" "$DIFY_WEB_PORT")
    fi

    # ── Infra config ──
    if svc_selected "postgres"; then
        echo ""
        echo -e "  ${BOLD}Configuration PostgreSQL${NC}"
        echo ""
        POSTGRES_PASSWORD=$(input_value "Mot de passe Postgres :" "$POSTGRES_PASSWORD")
        POSTGRES_PORT=$(input_value "Port Postgres :" "$POSTGRES_PORT")
    fi

    if svc_selected "redis"; then
        echo ""
        REDIS_PORT=$(input_value "Port Redis :" "$REDIS_PORT")
    fi

    # ── Écriture .env ──
    {
        echo "# ═══ Mascarade .env ═══"
        echo "# Généré par install.sh le $(date '+%Y-%m-%d %H:%M')"
        echo ""

        if svc_selected "core" || svc_selected "litellm"; then
            echo "# LLM API Keys"
            echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
            echo "OPENAI_API_KEY=${OPENAI_API_KEY}"
            echo "MISTRAL_API_KEY=${MISTRAL_API_KEY}"
            echo ""
        fi

        if svc_selected "core"; then
            echo "# Notion"
            echo "NOTION_API_KEY=${NOTION_API_KEY}"
            echo ""
            echo "# Auth"
            echo "MASCARADE_API_KEY=${MASCARADE_API_KEY}"
            echo ""
            echo "# Core"
            echo "CORE_HOST=0.0.0.0"
            echo "CORE_PORT=${CORE_PORT}"
            echo ""
            echo "# Default LLM"
            echo "DEFAULT_PROVIDER=${DEFAULT_PROVIDER}"
            echo "DEFAULT_MODEL=${DEFAULT_MODEL}"
            echo ""
        fi

        if svc_selected "api"; then
            echo "# API Gateway"
            echo "API_HOST=0.0.0.0"
            echo "API_PORT=${API_PORT}"
            echo "CORE_URL=http://core:${CORE_PORT}"
            echo ""
        fi

        if svc_selected "postgres"; then
            echo "# PostgreSQL"
            echo "POSTGRES_HOST=postgres"
            echo "POSTGRES_PORT=${POSTGRES_PORT}"
            echo "POSTGRES_USER=mascarade"
            echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
            echo "POSTGRES_DB=mascarade"
            echo ""
        fi

        if svc_selected "redis"; then
            echo "# Redis"
            echo "REDIS_HOST=redis"
            echo "REDIS_PORT=${REDIS_PORT}"
            echo ""
        fi

        if svc_selected "langfuse"; then
            echo "# Langfuse"
            echo "LANGFUSE_PORT=${LANGFUSE_PORT}"
            echo "LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}"
            echo "LANGFUSE_NEXT_PUBLIC_KEY=${LANGFUSE_NEXT_PUBLIC_KEY}"
            echo "ENCRYPTION_KEY=${ENCRYPTION_KEY}"
            echo "LANGFUSE_S3_EVENT_UPLOAD_ENABLED=false"
            echo ""
        fi

        if svc_selected "litellm"; then
            echo "# LiteLLM"
            echo "LITELLM_PORT=${LITELLM_PORT}"
            echo ""
        fi

        if svc_selected "n8n"; then
            echo "# n8n"
            echo "N8N_PORT=${N8N_PORT}"
            echo ""
        fi

        if svc_selected "dify"; then
            echo "# Dify"
            echo "DIFY_API_PORT=${DIFY_API_PORT}"
            echo "DIFY_WEB_PORT=${DIFY_WEB_PORT}"
            echo ""
        fi

        if svc_selected "ollama"; then
            echo "# Ollama"
            echo "OLLAMA_PORT=${OLLAMA_PORT}"
            echo ""
        fi

        if svc_selected "grafana"; then
            echo "# Grafana"
            echo "GRAFANA_PORT=${GRAFANA_PORT}"
            echo ""
        fi

        if svc_selected "prometheus"; then
            echo "# Prometheus"
            echo "PROMETHEUS_PORT=${PROMETHEUS_PORT}"
            echo ""
        fi

    } > "$env_file"

    ok ".env sauvegardé ($(wc -l < "$env_file") lignes)"
}

# ══════════════════════════════════════════════
# Génération docker-compose.yml
# ══════════════════════════════════════════════
generate_compose() {
    local compose_file="$REPO_DIR/docker-compose.yml"
    local network="mascarade-network"

    {
        echo "# docker-compose.yml — Généré par install.sh le $(date '+%Y-%m-%d %H:%M')"
        echo "# Services actifs : $(for id in "${SVC_IDS[@]}"; do [[ "${SVC_ON[$id]}" == "1" ]] && printf '%s ' "$id"; done)"
        echo ""
        echo "services:"

        # ── Core ──
        if svc_selected "core"; then
            cat << 'YAML'
  core:
    build:
      context: .
      dockerfile: deploy/Dockerfile.core
    env_file: .env
    volumes:
      - core-data:/app/data
    restart: unless-stopped
YAML
            echo "    ports:"
            echo "      - \"${CORE_PORT:-8100}:${CORE_PORT:-8100}\""
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── API ──
        if svc_selected "api"; then
            cat << 'YAML'
  api:
    build:
      context: .
      dockerfile: deploy/Dockerfile.api
    env_file: .env
YAML
            echo "    ports:"
            echo "      - \"${API_PORT:-3000}:${API_PORT:-3000}\""
            echo "    environment:"
            echo "      - CORE_URL=http://core:${CORE_PORT:-8100}"
            echo "      - API_PORT=${API_PORT:-3000}"
            if svc_selected "core"; then
                echo "    depends_on:"
                echo "      - core"
            fi
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Redis ──
        if svc_selected "redis"; then
            echo "  redis:"
            echo "    image: redis:7-alpine"
            echo "    ports:"
            echo "      - \"127.0.0.1:${REDIS_PORT:-6379}:6379\""
            echo "    volumes:"
            echo "      - redis-data:/data"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── PostgreSQL ──
        if svc_selected "postgres"; then
            echo "  postgres:"
            echo "    image: postgres:16-alpine"
            echo "    ports:"
            echo "      - \"127.0.0.1:${POSTGRES_PORT:-5432}:5432\""
            echo "    environment:"
            echo "      POSTGRES_USER: mascarade"
            echo "      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD:-changeme}"
            echo "      POSTGRES_DB: mascarade"
            echo "    volumes:"
            echo "      - postgres-data:/var/lib/postgresql/data"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Qdrant ──
        if svc_selected "qdrant"; then
            echo "  qdrant:"
            echo "    image: qdrant/qdrant:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${QDRANT_PORT:-6333}:6333\""
            echo "    volumes:"
            echo "      - qdrant-data:/qdrant/storage"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Ollama ──
        if svc_selected "ollama"; then
            echo "  ollama:"
            echo "    image: ollama/ollama:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${OLLAMA_PORT:-11434}:11434\""
            echo "    volumes:"
            echo "      - ollama-data:/root/.ollama"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Open WebUI ──
        if svc_selected "open-webui"; then
            echo "  open-webui:"
            echo "    image: ghcr.io/open-webui/open-webui:main"
            echo "    ports:"
            echo "      - \"127.0.0.1:${OPEN_WEBUI_PORT:-8080}:8080\""
            echo "    environment:"
            echo "      - OLLAMA_BASE_URL=http://ollama:11434"
            if svc_selected "ollama"; then
                echo "    depends_on:"
                echo "      - ollama"
            fi
            echo "    volumes:"
            echo "      - open-webui-data:/app/backend/data"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── ClickHouse ──
        if svc_selected "clickhouse"; then
            echo "  clickhouse:"
            echo "    image: clickhouse/clickhouse-server:latest"
            echo "    volumes:"
            echo "      - clickhouse-data:/var/lib/clickhouse"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Langfuse ──
        if svc_selected "langfuse"; then
            echo "  langfuse:"
            echo "    image: langfuse/langfuse:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${LANGFUSE_PORT:-3200}:3000\""
            echo "    environment:"
            echo "      - DATABASE_URL=postgresql://mascarade:\${POSTGRES_PASSWORD:-changeme}@postgres:5432/mascarade"
            echo "      - NEXTAUTH_URL=http://localhost:${LANGFUSE_PORT:-3200}"
            echo "      - NEXTAUTH_SECRET=\${LANGFUSE_SECRET_KEY}"
            echo "      - SALT=\${ENCRYPTION_KEY}"
            echo "      - ENCRYPTION_KEY=\${ENCRYPTION_KEY}"
            echo "      - LANGFUSE_S3_EVENT_UPLOAD_ENABLED=false"
            if svc_selected "clickhouse"; then
                echo "      - CLICKHOUSE_URL=http://clickhouse:8123"
            fi
            echo "    depends_on:"
            svc_selected "postgres"   && echo "      - postgres"
            svc_selected "clickhouse" && echo "      - clickhouse"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── LiteLLM ──
        if svc_selected "litellm"; then
            echo "  litellm:"
            echo "    image: ghcr.io/berriai/litellm:main-latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${LITELLM_PORT:-4000}:4000\""
            echo "    env_file: .env"
            if svc_selected "redis"; then
                echo "    environment:"
                echo "      - REDIS_HOST=redis"
                echo "      - REDIS_PORT=6379"
            fi
            echo "    volumes:"
            echo "      - ./tools/litellm-config.yaml:/app/config.yaml:ro"
            echo "    command: [\"--config\", \"/app/config.yaml\"]"
            if svc_selected "redis"; then
                echo "    depends_on:"
                echo "      - redis"
            fi
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── n8n ──
        if svc_selected "n8n"; then
            echo "  n8n:"
            echo "    image: n8nio/n8n:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${N8N_PORT:-5678}:5678\""
            echo "    environment:"
            echo "      - DB_TYPE=postgresdb"
            echo "      - DB_POSTGRESDB_HOST=postgres"
            echo "      - DB_POSTGRESDB_PORT=5432"
            echo "      - DB_POSTGRESDB_DATABASE=mascarade"
            echo "      - DB_POSTGRESDB_USER=mascarade"
            echo "      - DB_POSTGRESDB_PASSWORD=\${POSTGRES_PASSWORD:-changeme}"
            echo "    volumes:"
            echo "      - n8n-data:/home/node/.n8n"
            if svc_selected "postgres"; then
                echo "    depends_on:"
                echo "      - postgres"
            fi
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Dify ──
        if svc_selected "dify"; then
            echo "  dify-api:"
            echo "    image: langgenius/dify-api:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${DIFY_API_PORT:-5001}:5001\""
            echo "    environment:"
            echo "      - DB_USERNAME=mascarade"
            echo "      - DB_PASSWORD=\${POSTGRES_PASSWORD:-changeme}"
            echo "      - DB_HOST=postgres"
            echo "      - DB_PORT=5432"
            echo "      - DB_DATABASE=mascarade"
            echo "      - REDIS_HOST=redis"
            echo "      - REDIS_PORT=6379"
            echo "    depends_on:"
            svc_selected "postgres" && echo "      - postgres"
            svc_selected "redis"    && echo "      - redis"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
            echo "  dify-web:"
            echo "    image: langgenius/dify-web:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${DIFY_WEB_PORT:-3500}:3000\""
            echo "    environment:"
            echo "      - CONSOLE_API_URL=http://dify-api:5001"
            echo "    depends_on:"
            echo "      - dify-api"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
            echo "  dify-worker:"
            echo "    image: langgenius/dify-api:latest"
            echo "    command: celery -A app.celery worker"
            echo "    environment:"
            echo "      - DB_USERNAME=mascarade"
            echo "      - DB_PASSWORD=\${POSTGRES_PASSWORD:-changeme}"
            echo "      - DB_HOST=postgres"
            echo "      - DB_PORT=5432"
            echo "      - DB_DATABASE=mascarade"
            echo "      - REDIS_HOST=redis"
            echo "      - REDIS_PORT=6379"
            echo "    depends_on:"
            echo "      - dify-api"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Grafana ──
        if svc_selected "grafana"; then
            echo "  grafana:"
            echo "    image: grafana/grafana:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${GRAFANA_PORT:-3001}:3000\""
            echo "    volumes:"
            echo "      - grafana-data:/var/lib/grafana"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Prometheus ──
        if svc_selected "prometheus"; then
            echo "  prometheus:"
            echo "    image: prom/prometheus:latest"
            echo "    ports:"
            echo "      - \"127.0.0.1:${PROMETHEUS_PORT:-9090}:9090\""
            echo "    volumes:"
            echo "      - prometheus-data:/prometheus"
            echo "    restart: unless-stopped"
            echo "    networks:"
            echo "      - ${network}"
            echo ""
        fi

        # ── Volumes ──
        echo "volumes:"
        svc_selected "core"       && echo "  core-data:"
        svc_selected "redis"      && echo "  redis-data:"
        svc_selected "postgres"   && echo "  postgres-data:"
        svc_selected "qdrant"     && echo "  qdrant-data:"
        svc_selected "ollama"     && echo "  ollama-data:"
        svc_selected "open-webui" && echo "  open-webui-data:"
        svc_selected "clickhouse" && echo "  clickhouse-data:"
        svc_selected "n8n"        && echo "  n8n-data:"
        svc_selected "grafana"    && echo "  grafana-data:"
        svc_selected "prometheus" && echo "  prometheus-data:"
        echo ""

        # ── Network ──
        echo "networks:"
        echo "  ${network}:"
        echo "    driver: bridge"

    } > "$compose_file"

    ok "docker-compose.yml généré ($(grep -c '^\s\s[a-z]' "$compose_file") services)"
}

# ══════════════════════════════════════════════
# Auto-sélection des dépendances
# ══════════════════════════════════════════════
resolve_dependencies() {
    local changed=true
    while [[ "$changed" == true ]]; do
        changed=false

        # Langfuse requiert PostgreSQL + ClickHouse
        if svc_selected "langfuse"; then
            if ! svc_selected "postgres"; then
                SVC_ON["postgres"]="1"; changed=true
                warn "PostgreSQL activé automatiquement (requis par Langfuse)"
            fi
            if ! svc_selected "clickhouse"; then
                SVC_ON["clickhouse"]="1"; changed=true
                warn "ClickHouse activé automatiquement (requis par Langfuse)"
            fi
        fi

        # Dify requiert PostgreSQL + Redis
        if svc_selected "dify"; then
            if ! svc_selected "postgres"; then
                SVC_ON["postgres"]="1"; changed=true
                warn "PostgreSQL activé automatiquement (requis par Dify)"
            fi
            if ! svc_selected "redis"; then
                SVC_ON["redis"]="1"; changed=true
                warn "Redis activé automatiquement (requis par Dify)"
            fi
        fi

        # n8n requiert PostgreSQL
        if svc_selected "n8n"; then
            if ! svc_selected "postgres"; then
                SVC_ON["postgres"]="1"; changed=true
                warn "PostgreSQL activé automatiquement (requis par n8n)"
            fi
        fi

        # LiteLLM bénéficie de Redis
        if svc_selected "litellm" && ! svc_selected "redis"; then
            SVC_ON["redis"]="1"; changed=true
            warn "Redis activé automatiquement (cache LiteLLM)"
        fi

        # Open WebUI bénéficie d'Ollama
        if svc_selected "open-webui" && ! svc_selected "ollama"; then
            warn "Open WebUI sans Ollama : configurez OLLAMA_BASE_URL manuellement"
            break
        fi
    done
}

# ══════════════════════════════════════════════
# Installation des dépendances locales
# ══════════════════════════════════════════════
install_local_deps() {
    if svc_selected "core" && command -v python3 &>/dev/null; then
        log "Installation du Core Python..."
        cd "$REPO_DIR/core"
        if [[ ! -d ".venv" ]]; then
            python3 -m venv .venv
            ok "Virtualenv créé"
        fi
        .venv/bin/pip install --upgrade pip -q 2>&1 | tail -1
        .venv/bin/pip install -e ".[dev]" -q 2>&1 | tail -1
        ok "Dépendances Python installées"
        cd "$REPO_DIR"
    fi

    if svc_selected "api" && command -v npm &>/dev/null; then
        log "Installation de l'API Node.js..."
        cd "$REPO_DIR/api"
        npm install --silent 2>&1 | tail -1
        npm run build --silent 2>&1 || warn "Build TS échoué (non bloquant)"
        ok "Dépendances Node.js installées"
        cd "$REPO_DIR"
    fi
}

# ══════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════
run_tests() {
    if svc_selected "core" && [[ -d "$REPO_DIR/core/.venv" ]]; then
        log "Tests Python..."
        cd "$REPO_DIR/core"
        if .venv/bin/python -m pytest -q 2>&1; then
            ok "Tests passés"
        else
            warn "Certains tests ont échoué"
        fi
        cd "$REPO_DIR"
    fi
}

# ══════════════════════════════════════════════
# Démarrage Docker
# ══════════════════════════════════════════════
start_services() {
    log "Build des images..."
    docker compose build 2>&1 | tail -5
    ok "Images prêtes"

    log "Démarrage des containers..."
    docker compose up -d 2>&1
    ok "Containers lancés"

    echo ""
    log "Health checks..."
    sleep 4

    if svc_selected "core"; then
        if curl -sf "http://localhost:${CORE_PORT:-8100}/health" > /dev/null 2>&1; then
            ok "Core :${CORE_PORT:-8100}"
        else
            warn "Core ne répond pas encore"
        fi
    fi

    if svc_selected "api"; then
        if curl -sf "http://localhost:${API_PORT:-3000}/health" > /dev/null 2>&1; then
            ok "API :${API_PORT:-3000}"
        else
            warn "API ne répond pas encore"
        fi
    fi

    for id in $(selected_in_cat "tools") $(selected_in_cat "infra"); do
        local port="${SVC_PORT[$id]}"
        [[ "$port" == "—" ]] && continue
        local container
        container=$(docker compose ps --format '{{.Name}}' 2>/dev/null | grep -i "$id" | head -1)
        if [[ -n "$container" ]]; then
            local state
            state=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
            if [[ "$state" == "running" ]]; then
                ok "${SVC_LABEL[$id]} :${port}"
            else
                warn "${SVC_LABEL[$id]} — $state"
            fi
        fi
    done
}

# ══════════════════════════════════════════════
# Récapitulatif final
# ══════════════════════════════════════════════
show_summary() {
    echo ""
    line
    echo ""
    echo -e "  ${GREEN}${BOLD}Installation terminée !${NC}"
    echo ""

    # Tableau des services
    echo -e "  ${BOLD}Services déployés :${NC}"
    echo ""
    printf "  ${DIM}%-20s %-8s %s${NC}\n" "SERVICE" "PORT" "STATUT"
    line

    for id in "${SVC_IDS[@]}"; do
        if svc_selected "$id"; then
            local port="${SVC_PORT[$id]}"
            [[ "$port" == "—" ]] && port="interne"
            printf "  %-20s %-8s ${GREEN}actif${NC}\n" "${SVC_LABEL[$id]}" ":${port}"
        fi
    done

    echo ""
    echo -e "  ${BOLD}Commandes utiles :${NC}"
    echo -e "  ${DIM}├${NC} docker compose ps              ${DIM}# Statut${NC}"
    echo -e "  ${DIM}├${NC} docker compose logs -f          ${DIM}# Logs${NC}"
    echo -e "  ${DIM}├${NC} docker compose down             ${DIM}# Arrêter${NC}"
    echo -e "  ${DIM}├${NC} docker compose up -d            ${DIM}# Relancer${NC}"
    echo -e "  ${DIM}├${NC} ./install.sh update             ${DIM}# Mise à jour TUI${NC}"
    echo -e "  ${DIM}└${NC} ./deploy/update.sh              ${DIM}# Mise à jour rapide${NC}"

    if svc_selected "api" && [[ -n "${MASCARADE_API_KEY:-}" ]]; then
        echo ""
        echo -e "  ${BOLD}Test rapide :${NC}"
        echo -e "  curl -sH 'Authorization: Bearer \$MASCARADE_API_KEY' \\"
        echo -e "    http://localhost:${API_PORT:-3000}/api/agents/metrics | python3 -m json.tool"
    fi

    echo ""
    line
    echo -e "  ${DIM}mascarade v0.1.0${NC}"
    echo ""
}

# ══════════════════════════════════════════════════════════════════════
#
#  MODE UPDATE — TUI de mise à jour des services
#
# ══════════════════════════════════════════════════════════════════════

# Checkbox pour l'update : détecte les services depuis docker-compose.yml
update_checkbox_select() {
    local services=("$@")
    local count=${#services[@]}
    local cursor=0

    # Tout sélectionné par défaut
    declare -gA UPD_ON=()
    for s in "${services[@]}"; do UPD_ON[$s]="1"; done

    tput civis 2>/dev/null || true

    while true; do
        echo -e "\n  ${BOLD}Services à mettre à jour${NC}\n"

        for i in "${!services[@]}"; do
            local s="${services[$i]}"
            local check=" "
            [[ "${UPD_ON[$s]}" == "1" ]] && check="${GREEN}✓${NC}"

            # Récupérer statut du container
            local status_str="${DIM}(inconnu)${NC}"
            local container_name
            container_name=$(docker compose ps --format '{{.Name}}\t{{.Status}}' 2>/dev/null | grep -i "${s}" | head -1)
            if [[ -n "$container_name" ]]; then
                local cstatus
                cstatus=$(echo "$container_name" | cut -f2)
                if [[ "$cstatus" == *"Up"* ]]; then
                    status_str="${GREEN}running${NC}"
                elif [[ "$cstatus" == *"Exit"* ]]; then
                    status_str="${RED}exited${NC}"
                else
                    status_str="${YELLOW}${cstatus}${NC}"
                fi
            else
                status_str="${DIM}not running${NC}"
            fi

            if [[ $i -eq $cursor ]]; then
                echo -e "  ${WHITE}${BOLD} ▶ [${check}${WHITE}${BOLD}] ${s}${NC}  ${status_str}"
            else
                echo -e "  ${DIM}   [${check}${DIM}] ${s}${NC}  ${status_str}"
            fi
        done

        local sel=0
        for s in "${services[@]}"; do [[ "${UPD_ON[$s]}" == "1" ]] && ((sel++)); done
        echo ""
        echo -e "  ${DIM}↑/↓ naviguer  ␣ (dé)cocher  a tout  n rien  Entrée valider${NC}"
        echo -e "  ${DIM}${sel}/${count} sélectionné(s)${NC}"

        read -rsn1 key
        case "$key" in
            A) ((cursor > 0)) && ((cursor--)) ;;
            B) ((cursor < count - 1)) && ((cursor++)) ;;
            ' ')
                local s="${services[$cursor]}"
                [[ "${UPD_ON[$s]}" == "1" ]] && UPD_ON[$s]="0" || UPD_ON[$s]="1"
                ;;
            a|A) for s in "${services[@]}"; do UPD_ON[$s]="1"; done ;;
            n|N) for s in "${services[@]}"; do UPD_ON[$s]="0"; done ;;
            '') break ;;
        esac

        local total_lines=$((count + 5))
        tput cuu "$total_lines" 2>/dev/null
        for ((i = 0; i < total_lines; i++)); do
            tput el 2>/dev/null; tput cud1 2>/dev/null
        done
        tput cuu "$total_lines" 2>/dev/null
    done

    tput cnorm 2>/dev/null || true
}

run_update() {
    banner

    echo -e "  ${BOLD}Mise à jour de Mascarade${NC}"
    echo -e "  ${DIM}Sélectionne les services à mettre à jour${NC}"

    # ── Vérifier docker-compose.yml ──
    if [[ ! -f "$REPO_DIR/docker-compose.yml" ]]; then
        err "Pas de docker-compose.yml trouvé. Lance d'abord ./install.sh"
        exit 1
    fi

    # ── Détecter les services du compose ──
    local compose_services=()
    while IFS= read -r svc; do
        [[ -n "$svc" ]] && compose_services+=("$svc")
    done < <(docker compose config --services 2>/dev/null)

    if [[ ${#compose_services[@]} -eq 0 ]]; then
        err "Aucun service trouvé dans docker-compose.yml"
        exit 1
    fi

    # ── Statut actuel ──
    section "Statut actuel"
    printf "  ${DIM}%-20s %-12s %-20s${NC}\n" "SERVICE" "STATUT" "IMAGE"
    line
    for svc in "${compose_services[@]}"; do
        local status_col="${DIM}arrêté${NC}"
        local image="—"
        local cname
        cname=$(docker compose ps --format '{{.Name}}\t{{.Status}}\t{{.Image}}' 2>/dev/null | grep -i "${svc}" | head -1)
        if [[ -n "$cname" ]]; then
            local cstatus cimage
            cstatus=$(echo "$cname" | cut -f2)
            cimage=$(echo "$cname" | cut -f3)
            image="${cimage:-—}"
            if [[ "$cstatus" == *"Up"* ]]; then
                status_col="${GREEN}running${NC}"
            elif [[ "$cstatus" == *"Exit"* ]]; then
                status_col="${RED}exited${NC}"
            else
                status_col="${YELLOW}${cstatus}${NC}"
            fi
        fi
        printf "  %-20s ${status_col}  %-20s\n" "$svc" "$image"
    done

    # ── Sélection des services à updater ──
    section "Sélection"
    update_checkbox_select "${compose_services[@]}"

    local to_update=()
    for svc in "${compose_services[@]}"; do
        [[ "${UPD_ON[$svc]:-0}" == "1" ]] && to_update+=("$svc")
    done

    if [[ ${#to_update[@]} -eq 0 ]]; then
        err "Aucun service sélectionné pour la mise à jour."
        exit 1
    fi

    echo ""
    echo -e "  ${BOLD}Services à mettre à jour :${NC}"
    for svc in "${to_update[@]}"; do
        echo -e "    ${CYAN}▸${NC} $svc"
    done
    echo ""
    if ! confirm "Lancer la mise à jour ?"; then
        exit 0
    fi

    # ── Choix de la stratégie d'update ──
    section "Stratégie"
    menu_select "Comment mettre à jour ?" \
        "Pull images + rebuild + restart (complet)" \
        "Rebuild seulement (images locales, core/api)" \
        "Restart seulement (pas de rebuild)" \
        "Pull images seulement (sans restart)"
    local strategy=$?

    # ── Git pull ──
    local has_build_services=false
    for svc in "${to_update[@]}"; do
        if [[ "$svc" == "core" || "$svc" == "api" ]]; then
            has_build_services=true; break
        fi
    done

    if [[ "$has_build_services" == true && $strategy -le 1 ]]; then
        section "Git"
        if confirm "Faire un git pull avant le build ?"; then
            if git pull --ff-only 2>&1; then
                ok "Code à jour"
            else
                warn "git pull échoué (merge conflict ?)"
                if ! confirm "Continuer quand même ?"; then
                    exit 1
                fi
            fi
        fi
    fi

    # ── Tests avant update ──
    if [[ "$has_build_services" == true && $strategy -le 1 ]]; then
        section "Tests"
        if [[ -d "$REPO_DIR/core/.venv" ]]; then
            if confirm "Lancer les tests avant le déploiement ?"; then
                cd "$REPO_DIR/core"
                if .venv/bin/python -m pytest -q 2>&1; then
                    ok "Tests passés"
                else
                    warn "Certains tests ont échoué"
                    if ! confirm "Continuer malgré les échecs ?"; then
                        exit 1
                    fi
                fi
                cd "$REPO_DIR"
            fi
        fi
    fi

    # ── Exécution de la mise à jour ──
    section "Mise à jour"

    case $strategy in
        0) # Pull + rebuild + restart
            log "Pull des images..."
            for svc in "${to_update[@]}"; do
                # Les services avec build (core, api) ne se pull pas
                if [[ "$svc" != "core" && "$svc" != "api" ]]; then
                    docker compose pull "$svc" 2>&1 | tail -1
                    ok "Pull $svc"
                fi
            done

            log "Build des services locaux..."
            for svc in "${to_update[@]}"; do
                if [[ "$svc" == "core" || "$svc" == "api" ]]; then
                    docker compose build --no-cache "$svc" 2>&1 | tail -2
                    ok "Build $svc"
                fi
            done

            log "Restart des services..."
            docker compose up -d --force-recreate "${to_update[@]}" 2>&1
            ok "Services redémarrés"
            ;;

        1) # Rebuild seulement
            log "Rebuild des services..."
            for svc in "${to_update[@]}"; do
                if [[ "$svc" == "core" || "$svc" == "api" ]]; then
                    docker compose build --no-cache "$svc" 2>&1 | tail -2
                    ok "Build $svc"
                else
                    warn "$svc — pas de Dockerfile, skip build"
                fi
            done

            log "Restart..."
            docker compose up -d --force-recreate "${to_update[@]}" 2>&1
            ok "Services redémarrés"
            ;;

        2) # Restart seulement
            log "Restart des services..."
            docker compose restart "${to_update[@]}" 2>&1
            ok "Services redémarrés"
            ;;

        3) # Pull seulement
            log "Pull des images..."
            for svc in "${to_update[@]}"; do
                if [[ "$svc" != "core" && "$svc" != "api" ]]; then
                    docker compose pull "$svc" 2>&1 | tail -1
                    ok "Pull $svc"
                else
                    warn "$svc — image locale, rien à pull"
                fi
            done
            echo ""
            log "Images mises à jour. Lance 'docker compose up -d' pour appliquer."
            ;;
    esac

    # ── Health checks ──
    if [[ $strategy -le 2 ]]; then
        section "Health checks"
        sleep 3

        local all_healthy=true
        for svc in "${to_update[@]}"; do
            local port=""
            case "$svc" in
                core)       port=$(grep -oP 'CORE_PORT=\K\d+' "$REPO_DIR/.env" 2>/dev/null || echo "8100") ;;
                api)        port=$(grep -oP 'API_PORT=\K\d+' "$REPO_DIR/.env" 2>/dev/null || echo "3000") ;;
                langfuse)   port=$(grep -oP 'LANGFUSE_PORT=\K\d+' "$REPO_DIR/.env" 2>/dev/null || echo "3200") ;;
                litellm)    port=$(grep -oP 'LITELLM_PORT=\K\d+' "$REPO_DIR/.env" 2>/dev/null || echo "4000") ;;
                n8n)        port=$(grep -oP 'N8N_PORT=\K\d+' "$REPO_DIR/.env" 2>/dev/null || echo "5678") ;;
                grafana)    port=$(grep -oP 'GRAFANA_PORT=\K\d+' "$REPO_DIR/.env" 2>/dev/null || echo "3001") ;;
            esac

            if [[ -n "$port" ]]; then
                local retries=5 delay=2
                local healthy=false
                for ((r = 1; r <= retries; r++)); do
                    if curl -sf "http://localhost:${port}/health" > /dev/null 2>&1 \
                    || curl -sf "http://localhost:${port}/" > /dev/null 2>&1; then
                        healthy=true; break
                    fi
                    sleep "$delay"
                done
                if [[ "$healthy" == true ]]; then
                    ok "$svc :${port}"
                else
                    warn "$svc :${port} — ne répond pas"
                    all_healthy=false
                fi
            else
                # Vérifier par statut Docker
                local container
                container=$(docker compose ps --format '{{.Name}}' 2>/dev/null | grep -i "$svc" | head -1)
                if [[ -n "$container" ]]; then
                    local state
                    state=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
                    if [[ "$state" == "running" ]]; then
                        ok "$svc — running"
                    else
                        warn "$svc — $state"
                        all_healthy=false
                    fi
                fi
            fi
        done

        if [[ "$all_healthy" == false ]]; then
            echo ""
            warn "Certains services ne répondent pas. Vérifier :"
            echo -e "  ${DIM}docker compose logs --tail=30${NC}"
        fi
    fi

    # ── Résumé update ──
    echo ""
    line
    echo ""
    echo -e "  ${GREEN}${BOLD}Mise à jour terminée !${NC}"
    echo ""
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    echo ""
    line
    echo -e "  ${DIM}mascarade v0.1.0${NC}"
    echo ""
}

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

# Sous-commande : update
case "${1:-}" in
    update|up)
        run_update
        exit 0
        ;;
    -h|--help)
        echo "Usage: $0 [commande]"
        echo ""
        echo "Commandes:"
        echo "  (aucune)    Installation complète TUI"
        echo "  update      Mise à jour TUI des services existants"
        echo "  -h, --help  Afficher cette aide"
        exit 0
        ;;
    "")
        ;; # Mode install par défaut
    *)
        echo -e "${RED}Commande inconnue: $1${NC}"
        echo "Usage: $0 [update]"
        exit 1
        ;;
esac

banner

echo -e "  ${BOLD}Bienvenue dans l'installateur de Mascarade${NC}"
echo -e "  ${DIM}Orchestration LLM multi-providers${NC}"

# ── Étape 1 : Sélection des services ──
section "1. Sélection des services"
checkbox_select

# ── Vérifier qu'au moins un service est choisi ──
sel_count=0
for id in "${SVC_IDS[@]}"; do
    [[ "${SVC_ON[$id]}" == "1" ]] && ((sel_count++))
done
if [[ $sel_count -eq 0 ]]; then
    err "Aucun service sélectionné."
    exit 1
fi

# ── Résolution des dépendances ──
echo ""
log "Résolution des dépendances..."
resolve_dependencies

# Récap sélection
echo ""
echo -e "  ${BOLD}Services sélectionnés :${NC}"
for id in "${SVC_IDS[@]}"; do
    if svc_selected "$id"; then
        echo -e "    ${GREEN}✓${NC} ${SVC_LABEL[$id]} ${DIM}(:${SVC_PORT[$id]})${NC}"
    fi
done
echo ""
if ! confirm "Continuer avec cette sélection ?"; then
    exit 0
fi

# ── Étape 2 : Prérequis ──
section "2. Vérification des prérequis"
check_prerequisites

# ── Étape 3 : Configuration ──
section "3. Configuration"
if [[ -f "$REPO_DIR/.env" ]]; then
    if confirm "Un fichier .env existe. Le reconfigurer ?"; then
        configure_env
    else
        ok ".env conservé"
    fi
else
    configure_env
fi

# ── Étape 4 : Génération docker-compose.yml ──
section "4. Génération docker-compose.yml"
if [[ -f "$REPO_DIR/docker-compose.yml" ]]; then
    warn "docker-compose.yml existant sera remplacé"
fi
generate_compose

# ── Étape 5 : Installation dépendances locales ──
section "5. Dépendances locales"
install_local_deps

# ── Étape 6 : Tests ──
section "6. Tests"
if svc_selected "core" && [[ -d "$REPO_DIR/core/.venv" ]]; then
    if confirm "Lancer les tests ?"; then
        run_tests
    else
        warn "Tests ignorés"
    fi
else
    ok "Pas de tests à lancer"
fi

# ── Étape 7 : Démarrage ──
section "7. Démarrage"
menu_select "Comment procéder ?" \
    "Démarrer maintenant (docker compose up)" \
    "Ne pas démarrer (je le ferai plus tard)"
choice=$?

case $choice in
    0) start_services ;;
    1) ok "docker-compose.yml prêt, lance : docker compose up -d" ;;
esac

# ── Résumé ──
show_summary
