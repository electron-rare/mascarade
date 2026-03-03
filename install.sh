#!/usr/bin/env bash
# install.sh — Installation de Mascarade sur une VM fraiche
# Usage: ./install.sh [--skip-deps] [--skip-build]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# --- Couleurs ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[mascarade]${NC} $*"; }
ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }

# --- Args ---
SKIP_DEPS=false
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-deps)   SKIP_DEPS=true; shift ;;
        --skip-build)  SKIP_BUILD=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--skip-deps] [--skip-build]"
            echo ""
            echo "Options:"
            echo "  --skip-deps    Skip system dependency checks"
            echo "  --skip-build   Skip Docker build (configure only)"
            echo "  -h, --help     Show this help"
            exit 0
            ;;
        *) err "Option inconnue: $1"; exit 1 ;;
    esac
done

# ============================================================
# 1. Verification des pre-requis systeme
# ============================================================
log "Verification des pre-requis..."

check_cmd() {
    if command -v "$1" &>/dev/null; then
        ok "$1 trouve ($(command -v "$1"))"
        return 0
    else
        err "$1 introuvable"
        return 1
    fi
}

MISSING=0

if [[ "$SKIP_DEPS" == false ]]; then
    check_cmd docker   || MISSING=1
    check_cmd git      || MISSING=1
    check_cmd curl     || MISSING=1

    if ! docker compose version &>/dev/null; then
        err "docker compose (plugin) introuvable"
        MISSING=1
    else
        ok "docker compose $(docker compose version --short)"
    fi

    if [[ "$MISSING" -eq 1 ]]; then
        err "Pre-requis manquants. Installe-les puis relance le script."
        exit 1
    fi

    # Verifier que Docker tourne
    if ! docker info &>/dev/null; then
        err "Le daemon Docker ne tourne pas. Lance: systemctl start docker"
        exit 1
    fi
    ok "Docker daemon actif"
else
    warn "Skip verification des dependances (--skip-deps)"
fi

# ============================================================
# 2. Configuration .env
# ============================================================
log "Configuration de l'environnement..."

if [[ -f "$REPO_DIR/.env" ]]; then
    ok ".env existe deja"

    # Verifier que les cles critiques ne sont pas des placeholders
    PLACEHOLDERS=0
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        case "$key" in
            ANTHROPIC_API_KEY|OPENAI_API_KEY|MISTRAL_API_KEY|NOTION_API_KEY|NOTION_TOKEN)
                # Verifier les placeholders courants
                if [[ "$value" =~ ^(sk-ant-\.\.\.|sk-\.\.\.|ntn_\.\.\.|change-me|TODO|CHANGEME|your-key-here|)$ ]]; then
                    warn "$key est un placeholder — a remplir"
                    PLACEHOLDERS=$((PLACEHOLDERS + 1))
                fi
                ;;
        esac
    done < "$REPO_DIR/.env"

    if [[ "$PLACEHOLDERS" -gt 0 ]]; then
        warn "$PLACEHOLDERS cle(s) API a configurer dans .env"
    fi
else
    if [[ -f "$REPO_DIR/.env.example" ]]; then
        cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
        ok ".env cree depuis .env.example"
        warn "Edite .env et remplis les cles API avant de continuer"
        warn "  vim $REPO_DIR/.env"
        echo ""
        read -rp "Appuie sur Entree quand .env est configure... "
    else
        err "Ni .env ni .env.example trouves"
        exit 1
    fi
fi

# ============================================================
# 3. Reseau Docker
# ============================================================
log "Verification du reseau Docker..."

NETWORK="docker-studio-ai_default"
if docker network inspect "$NETWORK" &>/dev/null; then
    ok "Reseau $NETWORK existe"
else
    warn "Reseau $NETWORK introuvable — les services infra (Redis, Postgres, etc.) ne sont peut-etre pas lances"
    warn "Mascarade fonctionnera en standalone sans acces aux services partages"
fi

# ============================================================
# 4. Build des images Docker
# ============================================================
if [[ "$SKIP_BUILD" == false ]]; then
    log "Build des images Docker..."

    docker compose build 2>&1 | tail -5
    ok "Images buildees"
else
    warn "Skip build Docker (--skip-build)"
fi

# ============================================================
# 5. Lancement des services
# ============================================================
log "Demarrage des services..."

docker compose up -d
ok "Services demarres"

# ============================================================
# 6. Health check
# ============================================================
log "Verification du health..."

RETRIES=30
DELAY=2

check_health() {
    local url="$1"
    local name="$2"
    for i in $(seq 1 "$RETRIES"); do
        if curl -sf "$url" > /dev/null 2>&1; then
            ok "$name operationnel"
            return 0
        fi
        sleep "$DELAY"
    done
    err "$name ne repond pas apres $((RETRIES * DELAY))s"
    return 1
}

# Resoudre les ports depuis docker compose
resolve_host_port() {
    local service="$1"
    local container_port="$2"
    local mapping
    mapping="$(docker compose port "$service" "$container_port" 2>/dev/null | head -n1 || true)"
    if [[ -z "$mapping" ]]; then
        echo "$container_port"
        return
    fi
    echo "${mapping##*:}"
}

HEALTHY=true

CORE_PORT="$(resolve_host_port core 8100)"
check_health "http://localhost:${CORE_PORT}/health" "Core (port $CORE_PORT)" || HEALTHY=false

API_PORT="$(resolve_host_port api 3000)"
check_health "http://localhost:${API_PORT}/health" "API (port $API_PORT)" || HEALTHY=false

# ============================================================
# 7. Resultat
# ============================================================
echo ""
echo "========================================"
if [[ "$HEALTHY" == true ]]; then
    ok "Mascarade installe et operationnel"
    echo ""
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    log "Endpoints:"
    echo "  Core  : http://localhost:${CORE_PORT}/health"
    echo "  API   : http://localhost:${API_PORT}/health"
    echo ""
    log "Commandes utiles:"
    echo "  Logs       : docker compose logs -f"
    echo "  Mise a jour: ./deploy/update.sh"
    echo "  Stop       : docker compose down"
else
    err "Installation terminee mais certains services ne repondent pas"
    echo ""
    docker compose logs --tail=30
    exit 1
fi
echo "========================================"
