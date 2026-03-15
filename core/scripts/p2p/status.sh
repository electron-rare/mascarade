#!/usr/bin/env bash
# Check P2P network status across all machines
set -euo pipefail

echo "=== Mascarade P2P Network Status ==="
echo ""

check_node() {
    local remote=$1
    local label=$2
    local port=$3

    echo -n "  $label ($remote): "
    local status
    status=$(ssh -o ConnectTimeout=3 "$remote" "
        pid=\$(pgrep -f 'python.*p2p_node.py' 2>/dev/null | head -1)
        if [ -n \"\$pid\" ]; then
            echo -n 'RUNNING (pid='\$pid')'
            if [ -f /tmp/p2p_node.log ]; then
                peer_id=\$(head -1 /tmp/p2p_node.log | grep -oP 'PEER_ID=\K[^ ]+' 2>/dev/null || head -1 /tmp/p2p_node.log)
                echo -n \" \$peer_id\"
            fi
            echo ''
        else
            echo 'STOPPED'
        fi
    " 2>/dev/null) || status="UNREACHABLE"
    echo "$status"
}

check_node "root@192.168.0.119" "Photon VM (bootstrap)" 4001
check_node "cils@192.168.0.210" "CILS MacBook" 4001
check_node "kxkm@kxkm-ai" "KXKM AI" 4001

echo ""

# Check TCP connectivity
echo "  TCP connectivity:"
for target in "192.168.0.119:4001" "192.168.0.210:4001" "kxkm-ai:4001"; do
    host="${target%%:*}"
    port="${target##*:}"
    echo -n "    $target: "
    nc -z -w 2 "$host" "$port" 2>/dev/null && echo "OPEN" || echo "CLOSED"
done

echo ""
echo "=== Done ==="
