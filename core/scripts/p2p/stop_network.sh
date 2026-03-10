#!/usr/bin/env bash
# Stop all P2P nodes across the network
set -euo pipefail

echo "=== Stopping P2P Network ==="

for remote in "root@192.168.0.119" "cils@192.168.0.210" "kxkm@kxkm-ai" "clems@192.168.0.120"; do
    echo -n "  $remote: "
    ssh -o ConnectTimeout=5 "$remote" "pkill -f 'python.*p2p_node.py' 2>/dev/null && echo 'stopped' || echo 'not running'" 2>/dev/null || echo "unreachable"
done

echo ""
echo "=== All nodes stopped ==="
