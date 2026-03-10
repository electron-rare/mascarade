#!/usr/bin/env bash
# Deploy P2P module to all remote nodes
# Usage: ./scripts/p2p/deploy.sh [--sync-only]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
P2P_SRC="$CORE_DIR/mascarade/p2p"
INIT_SRC="$CORE_DIR/mascarade/__init__.py"

# Remote nodes
declare -A NODES=(
    ["root@192.168.0.119"]="/mascarade/core"
    ["cils@192.168.0.210"]="~/mascarade/core"
    ["kxkm@kxkm-ai"]="~/mascarade/core"
    ["clems@192.168.0.120"]="~/mascarade/core"
)

echo "=== Mascarade P2P Deploy ==="
echo "Source: $P2P_SRC"
echo ""

for remote in "${!NODES[@]}"; do
    dest="${NODES[$remote]}"
    echo "--- Deploying to $remote:$dest ---"

    # Ensure directory exists
    ssh -o ConnectTimeout=5 "$remote" "mkdir -p $dest/mascarade/p2p" 2>/dev/null || {
        echo "  SKIP: cannot connect to $remote"
        continue
    }

    # Sync __init__.py
    rsync -az "$INIT_SRC" "$remote:$dest/mascarade/__init__.py" 2>/dev/null || \
        scp -q "$INIT_SRC" "$remote:$dest/mascarade/__init__.py"

    # Sync P2P module (exclude pycache)
    rsync -az --delete --exclude='__pycache__' "$P2P_SRC/" "$remote:$dest/mascarade/p2p/" 2>/dev/null || {
        # Fallback: scp if rsync not available
        echo "  rsync unavailable, using scp..."
        scp -q -r "$P2P_SRC"/*.py "$remote:$dest/mascarade/p2p/"
    }

    # Verify import
    ssh -o ConnectTimeout=5 "$remote" "cd $dest && PYTHONPATH=$dest python3 -c 'from mascarade.p2p import BACKEND; print(f\"  OK backend={BACKEND}\")'" 2>/dev/null || {
        # Try with venv (CILS)
        ssh "$remote" "cd $dest && source .venv/bin/activate 2>/dev/null && python -c 'from mascarade.p2p import BACKEND; print(f\"  OK backend={BACKEND}\")'" 2>/dev/null || \
            echo "  WARN: import verification failed"
    }
done

echo ""
echo "=== Deploy complete ==="
