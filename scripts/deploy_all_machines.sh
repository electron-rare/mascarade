#!/usr/bin/env bash
# Deploy Mascarade to all 3 machines + smoke test
# Usage: bash scripts/deploy_all_machines.sh

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

MACHINES=(
    "root@192.168.0.119:/home/clems/mascarade"
    "root@192.168.0.120:/home/clems/mascarade"
    "kxkm@kxkm-ai:/home/kxkm/mascarade"
)

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $*"; }
err() { echo -e "${RED}[$(date +%H:%M:%S)] ERROR:${NC} $*"; }

# ── Deploy to each machine ──
for entry in "${MACHINES[@]}"; do
    host="${entry%%:*}"
    path="${entry#*:}"
    name="${host#*@}"

    log "═══ Deploying to $name ($path) ═══"

    # Check SSH connectivity
    if ! ssh -o ConnectTimeout=30 "$host" "echo ok" >/dev/null 2>&1; then
        warn "$name unreachable — skipping"
        continue
    fi

    # Pull latest
    log "$name: git pull..."
    ssh "$host" "cd $path 2>/dev/null && git pull origin main 2>&1 | tail -3" 2>&1 || {
        warn "$name: repo not found at $path — cloning..."
        ssh "$host" "git clone https://github.com/electron-rare/mascarade.git $path 2>&1 | tail -3" 2>&1 || {
            err "$name: clone failed"
            continue
        }
    }

    # Show version
    ssh "$host" "cd $path && git log --oneline -1" 2>&1 | while read -r line; do
        log "$name: $line"
    done

    # Rebuild if docker-compose exists
    if ssh "$host" "test -f $path/docker-compose.yml" 2>/dev/null; then
        log "$name: rebuilding containers..."
        ssh "$host" "cd $path && docker compose pull core api 2>/dev/null; docker compose up -d --build core api 2>&1 | tail -5" 2>&1 || warn "$name: docker rebuild failed"
    fi

    echo ""
done

# ── Smoke tests ──
log "═══ Smoke Tests ═══"

# Main VM (192.168.0.119)
log "Testing 192.168.0.119 (core:8100)..."
if curl -sf http://192.168.0.119:8100/health >/dev/null 2>&1; then
    HEALTH=$(curl -sf http://192.168.0.119:8100/health)
    PROVIDERS=$(echo "$HEALTH" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('providers',[])))" 2>/dev/null || echo "?")
    AGENTS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agents',0))" 2>/dev/null || echo "?")
    log "  Core: OK — ${PROVIDERS} providers, ${AGENTS} agents"
else
    warn "  Core: unreachable"
fi

if curl -sf http://192.168.0.119:3100/health >/dev/null 2>&1; then
    log "  API: OK"
else
    warn "  API: unreachable"
fi

# Tower (192.168.0.120)
log "Testing 192.168.0.120 (Tower)..."
if curl -sf http://192.168.0.120:8100/health >/dev/null 2>&1; then
    log "  Core: OK"
else
    warn "  Tower core: not running (expected if not deployed)"
fi

# kxkm-ai
log "Testing kxkm-ai..."
if ssh -o ConnectTimeout=30 kxkm@kxkm-ai "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null" >/dev/null 2>&1; then
    GPU=$(ssh kxkm@kxkm-ai "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader" 2>/dev/null)
    log "  GPU: $GPU"
else
    warn "  kxkm-ai: GPU not detected or unreachable"
fi

# P2P mesh check
log "Testing P2P mesh..."
if curl -sf http://192.168.0.119:8100/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('cluster' in str(d))" 2>/dev/null | grep -q True; then
    log "  P2P: cluster info present"
else
    warn "  P2P: no cluster info in health"
fi

echo ""
log "═══ Deploy complete ═══"
