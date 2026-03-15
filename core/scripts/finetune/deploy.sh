#!/usr/bin/env bash
# Deploy finetune module to all remote nodes
# Usage: ./scripts/finetune/deploy.sh [node_filter]
# Example: ./scripts/finetune/deploy.sh kxkm   (deploy only to kxkm)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
FT_SRC="$CORE_DIR/mascarade/finetune"
SCRIPTS_SRC="$CORE_DIR/scripts/finetune"
FILTER="${1:-}"

# ANSI
GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
RED='\033[31m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Remote nodes
declare -A NODES=(
    ["root@192.168.0.119"]="/mascarade/core"
    ["cils@192.168.0.210"]="~/mascarade/core"
    ["kxkm@kxkm-ai"]="~/mascarade/core"
    ["clems@192.168.0.120"]="~/mascarade/core"
)

echo -e "${BOLD}${CYAN}=== Mascarade Finetune Deploy ===${RESET}"
echo -e "Source: $FT_SRC"
echo ""

deployed=0
skipped=0
failed=0

for remote in "${!NODES[@]}"; do
    dest="${NODES[$remote]}"

    # Filter by node name if specified
    if [[ -n "$FILTER" ]] && [[ "$remote" != *"$FILTER"* ]]; then
        continue
    fi

    echo -e "${BOLD}--- $remote:$dest ---${RESET}"

    # Check connectivity
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$remote" "echo ok" >/dev/null 2>&1; then
        echo -e "  ${YELLOW}SKIP: cannot connect${RESET}"
        skipped=$((skipped + 1))
        continue
    fi

    # Create directories
    ssh "$remote" "mkdir -p $dest/mascarade/finetune/agents $dest/mascarade/finetune/p2p $dest/scripts/finetune" 2>/dev/null

    # Sync finetune module
    rsync -az --delete --exclude='__pycache__' \
        "$FT_SRC/" "$remote:$dest/mascarade/finetune/" 2>/dev/null || {
        echo -e "  ${DIM}rsync unavailable, using scp...${RESET}"
        scp -q -r "$FT_SRC"/*.py "$remote:$dest/mascarade/finetune/"
        scp -q -r "$FT_SRC/agents/"*.py "$remote:$dest/mascarade/finetune/agents/"
        scp -q -r "$FT_SRC/p2p/"*.py "$remote:$dest/mascarade/finetune/p2p/"
    }

    # Sync scripts
    rsync -az --exclude='__pycache__' \
        "$SCRIPTS_SRC/" "$remote:$dest/scripts/finetune/" 2>/dev/null || {
        scp -q "$SCRIPTS_SRC"/*.py "$remote:$dest/scripts/finetune/" 2>/dev/null || true
    }

    # Verify import
    verify_cmd="cd $dest && PYTHONPATH=$dest python3 -c 'from mascarade.finetune.registry import FinetuneRegistry; print(\"OK\")' 2>&1"
    result=$(ssh -o ConnectTimeout=5 "$remote" "$verify_cmd" 2>&1) || true

    if [[ "$result" == *"OK"* ]]; then
        echo -e "  ${GREEN}✓ Deployed + import verified${RESET}"
    else
        # Try with venv
        verify_venv="cd $dest && .venv/bin/python -c 'from mascarade.finetune.registry import FinetuneRegistry; print(\"OK\")' 2>&1"
        result2=$(ssh "$remote" "$verify_venv" 2>&1) || true
        if [[ "$result2" == *"OK"* ]]; then
            echo -e "  ${GREEN}✓ Deployed + import verified (venv)${RESET}"
        else
            echo -e "  ${YELLOW}⚠ Deployed but import failed${RESET}"
            echo -e "  ${DIM}$result${RESET}"
        fi
    fi

    deployed=$((deployed + 1))
done

echo ""
echo -e "${BOLD}${CYAN}=== Results: $deployed deployed, $skipped skipped ===${RESET}"
