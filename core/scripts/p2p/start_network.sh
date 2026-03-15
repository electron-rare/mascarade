#!/usr/bin/env bash
# Start the P2P network across all machines
# Usage: ./scripts/p2p/start_network.sh [--bootstrap-only] [--test]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOTSTRAP_ONLY=false
RUN_TEST=false

for arg in "$@"; do
    case $arg in
        --bootstrap-only) BOOTSTRAP_ONLY=true ;;
        --test) RUN_TEST=true ;;
    esac
done

echo "=== Mascarade P2P Network Start ==="

# --- Step 1: Start bootstrap node on VM ---
echo ""
echo "--- [1/4] Starting bootstrap node (192.168.0.119) ---"
ssh root@192.168.0.119 "pkill -f 'python3.*p2p_node.py' 2>/dev/null; sleep 1" || true

cat > /tmp/_p2p_bootstrap.py << 'PYEOF'
import asyncio, tempfile, sys, os, json
sys.path.insert(0, '/mascarade/core')
from mascarade.p2p.asyncio_node import MascaradeP2PNode

async def main():
    key_dir = os.path.expanduser("~/.mascarade/p2p")
    os.makedirs(key_dir, exist_ok=True)
    node = MascaradeP2PNode(listen_host='0.0.0.0', listen_port=4001, key_dir=key_dir)
    await node.start()
    info = {"peer_id": node.peer_id, "host": "192.168.0.119", "port": 4001}
    print(json.dumps(info), flush=True)
    await node.advertise_capabilities(
        capabilities=['llm-inference', 'gpu'],
        providers=['claude', 'ollama'],
        provider_models={'claude': ['claude-sonnet-4-6'], 'ollama': ['mistral-7b']},
        role='gpu', label='Photon VM',
        http_base_url='http://192.168.0.119:8100',
    )
    # Run indefinitely
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    await node.stop()

asyncio.run(main())
PYEOF

scp -q /tmp/_p2p_bootstrap.py root@192.168.0.119:/tmp/p2p_node.py
ssh root@192.168.0.119 'nohup python3 -u /tmp/p2p_node.py > /tmp/p2p_node.log 2>&1 &'

# Wait and get peer ID
sleep 3
BOOTSTRAP_INFO=$(ssh root@192.168.0.119 "head -1 /tmp/p2p_node.log")
BOOTSTRAP_PEER_ID=$(echo "$BOOTSTRAP_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['peer_id'])")
echo "  Bootstrap PeerID: $BOOTSTRAP_PEER_ID"
echo "  Listening on 192.168.0.119:4001"

if $BOOTSTRAP_ONLY; then
    echo ""
    echo "Bootstrap-only mode. Export for other nodes:"
    echo "  export MASCARADE_BOOTSTRAP_PEER=$BOOTSTRAP_PEER_ID"
    echo "  export MASCARADE_BOOTSTRAP_ADDR=192.168.0.119:4001"
    exit 0
fi

# --- Step 2: Start CILS node ---
echo ""
echo "--- [2/4] Starting CILS node (192.168.0.210) ---"
ssh cils@192.168.0.210 "pkill -f 'python.*p2p_node.py' 2>/dev/null; sleep 1" || true

cat > /tmp/_p2p_cils.py << PYEOF
import asyncio, os, sys
from mascarade.p2p.asyncio_node import MascaradeP2PNode

async def main():
    key_dir = os.path.expanduser("~/.mascarade/p2p")
    os.makedirs(key_dir, exist_ok=True)
    node = MascaradeP2PNode(
        listen_host='0.0.0.0', listen_port=4001, key_dir=key_dir,
        bootstrap_peers=[('$BOOTSTRAP_PEER_ID', '192.168.0.119', 4001)],
    )
    await node.start()
    print(f'PEER_ID={node.peer_id}', flush=True)
    await asyncio.sleep(1)
    await node.advertise_capabilities(
        capabilities=['mcp-host', 'kicad-validation', 'firmware-build'],
        role='worker', label='CILS MacBook',
        http_base_url='http://192.168.0.210:8100',
    )
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    await node.stop()

asyncio.run(main())
PYEOF

scp -q /tmp/_p2p_cils.py cils@192.168.0.210:/tmp/p2p_node.py
ssh cils@192.168.0.210 'cd ~/mascarade/core && source .venv/bin/activate && nohup python -u /tmp/p2p_node.py > /tmp/p2p_node.log 2>&1 &'
sleep 3
echo "  $(ssh cils@192.168.0.210 'head -1 /tmp/p2p_node.log')"

# --- Step 3: Start KXKM node ---
echo ""
echo "--- [3/4] Starting KXKM node (kxkm-ai) ---"
ssh kxkm@kxkm-ai "pkill -f 'python3.*p2p_node.py' 2>/dev/null; sleep 1" || true

cat > /tmp/_p2p_kxkm.py << PYEOF
import asyncio, os, sys
sys.path.insert(0, os.path.expanduser('~/mascarade/core'))
from mascarade.p2p.asyncio_node import MascaradeP2PNode

async def main():
    key_dir = os.path.expanduser("~/.mascarade/p2p")
    os.makedirs(key_dir, exist_ok=True)
    node = MascaradeP2PNode(
        listen_host='0.0.0.0', listen_port=4001, key_dir=key_dir,
        bootstrap_peers=[('$BOOTSTRAP_PEER_ID', '192.168.0.119', 4001)],
    )
    await node.start()
    print(f'PEER_ID={node.peer_id}', flush=True)
    await asyncio.sleep(1)
    await node.advertise_capabilities(
        capabilities=['compute', 'training'],
        role='compute', label='KXKM AI',
        http_base_url='http://kxkm-ai:8100',
    )
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    await node.stop()

asyncio.run(main())
PYEOF

scp -q /tmp/_p2p_kxkm.py kxkm@kxkm-ai:/tmp/p2p_node.py
ssh kxkm@kxkm-ai 'nohup python3 -u /tmp/p2p_node.py > /tmp/p2p_node.log 2>&1 &'
sleep 3
echo "  $(ssh kxkm@kxkm-ai 'head -1 /tmp/p2p_node.log')"

# --- Step 4: Status ---
echo ""
echo "--- [4/4] Network status ---"

if $RUN_TEST; then
    echo "Running connectivity test..."
    PYTHONPATH="/Users/electron/mascarade/core" python3 "$SCRIPT_DIR/test_mesh.py" "$BOOTSTRAP_PEER_ID"
else
    echo "All nodes started. Run with --test to verify mesh."
fi

echo ""
echo "=== P2P Network Running ==="
echo "Bootstrap: $BOOTSTRAP_PEER_ID @ 192.168.0.119:4001"
echo ""
echo "To stop:  $SCRIPT_DIR/stop_network.sh"
echo "To check: $SCRIPT_DIR/status.sh"
