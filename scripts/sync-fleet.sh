#!/usr/bin/env bash
# sync-fleet.sh — Synchronise mascarade sur toutes les machines du cluster
# Usage: ./sync-fleet.sh [push|pull|status] [--include-kill-life]
#
# push   : pousse le code local vers toutes les machines
# pull   : tire le dernier code sur toutes les machines (git pull)
# status : affiche l'etat de chaque machine
#
# Machines configurees via FLEET_HOSTS ou par defaut :
#   photon (root@192.168.0.119)
#   kxkm-ai (kxkm@100.87.54.119)
#   tower (clems@192.168.0.120)

set -euo pipefail

# --- Config ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Fleet definition: name|user@host|remote_path
FLEET=(
    "photon|root@192.168.0.119|/mascarade"
    "kxkm-ai|kxkm@100.87.54.119|/ai/saisail/mascarade"
    "tower|clems@192.168.0.120|/tmp/mascarade-test"
)

INCLUDE_KILL_LIFE=false
KILL_LIFE_LOCAL="${KILL_LIFE_LOCAL:-$HOME/Documents/Projets/Kill_LIFE}"
KILL_LIFE_REMOTE_BASE="/ai/saisail/Kill_LIFE"

ACTION="${1:-status}"
[[ "${2:-}" == "--include-kill-life" ]] && INCLUDE_KILL_LIFE=true

# --- Rsync excludes ---
RSYNC_EXCLUDES=(
    --exclude='.git'
    --exclude='node_modules'
    --exclude='.venv*'
    --exclude='__pycache__'
    --exclude='*.pyc'
    --exclude='.env'
    --exclude='.DS_Store'
    --exclude='dist/'
    --exclude='build/'
    --exclude='.pytest_cache'
    --exclude='.mypy_cache'
    --exclude='.ruff_cache'
    --exclude='htmlcov/'
    --exclude='.coverage'
    --exclude='finetune/runs/'
    --exclude='finetune/models/'
    --exclude='finetune/models_cache/'
    --exclude='finetune/models_local/'
    --exclude='finetune/logs/'
    --exclude='core-data/'
    --exclude='*.egg-info'
    --exclude='.ops/'
)

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1"; }

# --- Functions ---

check_host() {
    local name="$1" host="$2"
    if ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" 'true' 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

fleet_status() {
    local local_head
    local_head=$(git -C "$ROOT_DIR" log --oneline -1 2>/dev/null)
    echo -e "\n${BLUE}=== Fleet Status ===${NC}"
    echo -e "  Local: $local_head"
    echo ""

    for entry in "${FLEET[@]}"; do
        IFS='|' read -r name host path <<< "$entry"
        if ! check_host "$name" "$host"; then
            err "$name ($host) — unreachable"
            continue
        fi
        remote_head=$(ssh -o ConnectTimeout=3 "$host" "cd $path 2>/dev/null && git log --oneline -1 2>/dev/null || echo 'no repo'" 2>&1)
        if [[ "$remote_head" == *"no repo"* ]]; then
            warn "$name ($host) — no repo at $path"
        else
            local_hash=$(echo "$local_head" | cut -d' ' -f1)
            remote_hash=$(echo "$remote_head" | cut -d' ' -f1)
            if [[ "$local_hash" == "$remote_hash" ]]; then
                ok "$name ($host) — $remote_head"
            else
                warn "$name ($host) — $remote_head (behind)"
            fi
        fi
    done
    echo ""
}

fleet_push() {
    echo -e "\n${BLUE}=== Push to Fleet ===${NC}"
    info "Source: $ROOT_DIR"
    echo ""

    for entry in "${FLEET[@]}"; do
        IFS='|' read -r name host path <<< "$entry"
        if ! check_host "$name" "$host"; then
            err "$name ($host) — unreachable, skipping"
            continue
        fi

        info "Syncing to $name ($host:$path)..."
        rsync -azP --delete \
            "${RSYNC_EXCLUDES[@]}" \
            "$ROOT_DIR/" \
            "$host:$path/" \
            2>&1 | tail -3

        if [[ $? -eq 0 ]]; then
            ok "$name synced"
        else
            err "$name sync failed"
        fi
    done

    # Kill_LIFE sync
    if [[ "$INCLUDE_KILL_LIFE" == "true" ]] && [[ -d "$KILL_LIFE_LOCAL" ]]; then
        echo ""
        info "Syncing Kill_LIFE..."
        for entry in "${FLEET[@]}"; do
            IFS='|' read -r name host path <<< "$entry"
            if ! check_host "$name" "$host"; then continue; fi
            rsync -azP --delete \
                "${RSYNC_EXCLUDES[@]}" \
                "$KILL_LIFE_LOCAL/" \
                "$host:$KILL_LIFE_REMOTE_BASE/" \
                2>&1 | tail -3
            ok "$name Kill_LIFE synced"
        done
    fi

    echo ""
    ok "Fleet push complete"
}

fleet_pull() {
    echo -e "\n${BLUE}=== Pull on Fleet ===${NC}"

    # Local
    info "Pulling locally..."
    git -C "$ROOT_DIR" pull origin main 2>&1 | tail -2
    ok "Local updated"

    # Remote
    for entry in "${FLEET[@]}"; do
        IFS='|' read -r name host path <<< "$entry"
        if ! check_host "$name" "$host"; then
            err "$name ($host) — unreachable, skipping"
            continue
        fi

        info "Pulling on $name..."
        ssh -o ConnectTimeout=5 "$host" "cd $path && git fetch origin 2>/dev/null && git reset --hard origin/main 2>/dev/null" 2>&1 | tail -1
        ok "$name updated"
    done

    echo ""
    ok "Fleet pull complete"
}

# --- Main ---

case "$ACTION" in
    status|s)   fleet_status ;;
    push|p)     fleet_push ;;
    pull|l)     fleet_pull ;;
    *)
        echo "Usage: $0 [status|push|pull] [--include-kill-life]"
        echo ""
        echo "  status  Show sync state of all machines"
        echo "  push    Rsync code to all machines"
        echo "  pull    Git pull on all machines"
        exit 1
        ;;
esac
