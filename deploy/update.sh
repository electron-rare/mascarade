#!/usr/bin/env bash
# deploy/update.sh — Met à jour Mascarade sur la VM
# Usage: ./deploy/update.sh [--no-pull] [--service core|api]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
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
NO_PULL=false
SERVICE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-pull)  NO_PULL=true; shift ;;
        --service)  SERVICE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--no-pull] [--service core|api]"
            echo ""
            echo "Options:"
            echo "  --no-pull         Skip git pull (deploy local state)"
            echo "  --service NAME    Update only one service (core or api)"
            echo "  -h, --help        Show this help"
            exit 0
            ;;
        *) err "Option inconnue: $1"; exit 1 ;;
    esac
done

# --- Pre-checks ---
if ! command -v docker &>/dev/null; then
    err "docker introuvable"; exit 1
fi

if ! docker compose version &>/dev/null; then
    err "docker compose introuvable"; exit 1
fi

if [[ ! -f "$REPO_DIR/.env" ]]; then
    err ".env manquant — copie .env.example et remplis les clés"
    exit 1
fi

# --- Git pull ---
if [[ "$NO_PULL" == false ]]; then
    log "Pull des dernières modifications..."
    git pull --ff-only || { err "git pull a échoué (merge conflict ?)"; exit 1; }
    ok "Code à jour"
else
    warn "Skip git pull (--no-pull)"
fi

# --- Tests Python ---
log "Lancement des tests..."
if [[ -d "$REPO_DIR/core/.venv" ]]; then
    if (cd "$REPO_DIR/core" && .venv/bin/python -c "import pytest" >/dev/null 2>&1); then
        (cd "$REPO_DIR/core" && .venv/bin/python -m pytest -q 2>&1) || {
            err "Tests échoués — abandon du déploiement"
            exit 1
        }
        ok "Tests passés"
    else
        warn "pytest absent dans core/.venv — skip tests"
    fi
else
    warn "Pas de .venv — skip tests (les tests tourneront dans le build Docker)"
fi

# --- Build & restart ---
BUILD_ARGS=""
if [[ -n "$SERVICE" ]]; then
    log "Build et restart du service: $SERVICE"
    docker compose build --no-cache "$SERVICE"
    docker compose up -d "$SERVICE"
else
    log "Build et restart de tous les services..."
    docker compose build --no-cache
    docker compose up -d
fi

# --- Health check ---
log "Vérification du health..."
RETRIES=20
DELAY=2

check_health() {
    local url="$1"
    local name="$2"
    for i in $(seq 1 "$RETRIES"); do
        if curl -sf "$url" > /dev/null 2>&1; then
            ok "$name opérationnel"
            return 0
        fi
        sleep "$DELAY"
    done
    err "$name ne répond pas après $((RETRIES * DELAY))s"
    return 1
}

resolve_host_port() {
    local service="$1"
    local container_port="$2"
    local mapping
    mapping="$(docker compose port "$service" "$container_port" 2>/dev/null | head -n1 || true)"
    if [[ -z "$mapping" ]]; then
        return 1
    fi
    # Format attendu: 0.0.0.0:3100 ou [::]:3100
    echo "${mapping##*:}"
}

HEALTHY=true

if [[ -z "$SERVICE" || "$SERVICE" == "core" ]]; then
    CORE_PORT="$(resolve_host_port core 8100 || echo 8100)"
    check_health "http://localhost:${CORE_PORT}/health" "Core" || HEALTHY=false
fi

if [[ -z "$SERVICE" || "$SERVICE" == "api" ]]; then
    API_PORT="$(resolve_host_port api 3000 || echo 3000)"
    check_health "http://localhost:${API_PORT}/health" "API" || HEALTHY=false
fi

# --- Résultat ---
echo ""
if [[ "$HEALTHY" == true ]]; then
    ok "Mascarade mis à jour avec succès"
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
else
    err "Déploiement terminé mais certains services ne répondent pas"
    docker compose logs --tail=20
    exit 1
fi
