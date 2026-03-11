#!/usr/bin/env bash
# run_all.sh — Start full P2P mesh + mascarade server
# Usage: ./run_all.sh [start|stop|status|test]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

VM_HOST="192.168.0.119"
CILS_HOST="192.168.0.210"
TOWER_HOST="192.168.0.120"
KXKM_HOST="kxkm-ai"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${YELLOW}→${NC} $1"; }

# ───────────────────────────────────────────
cmd_start() {
    echo "=== Starting P2P Mesh ==="

    echo ""
    echo "1. VM Bootstrap + Relay"
    ssh root@$VM_HOST "pkill -f node_start_bootstrap 2>/dev/null; sleep 1; cd /mascarade/core && nohup python3 scripts/p2p/node_start_bootstrap.py </dev/null >/tmp/p2p_node.log 2>&1 &" 2>/dev/null && ok "VM started" || fail "VM start failed"
    sleep 3
    VM_LOG=$(ssh root@$VM_HOST "head -2 /tmp/p2p_node.log" 2>/dev/null)
    echo "$VM_LOG" | grep -q READY && ok "VM READY" || fail "VM not ready: $VM_LOG"

    echo ""
    echo "2. Workers"
    for spec in "cils@$CILS_HOST:CILS MacBook:kicad-validation,firmware-build,compute" "clems@$TOWER_HOST:Tower:compute,storage"; do
        IFS=: read -r ssh_target label caps <<< "$spec"
        ssh "$ssh_target" "lsof -ti:4001 2>/dev/null | xargs kill 2>/dev/null; sleep 1; cd ~/mascarade/core && P2P_CAPABILITIES=$caps P2P_LABEL='$label' nohup python3 scripts/p2p/task_handler_worker.py </dev/null >/tmp/p2p_node.log 2>&1 &" 2>/dev/null && ok "$label started" || fail "$label start failed"
    done
    sleep 4

    for spec in "cils@$CILS_HOST:CILS" "clems@$TOWER_HOST:Tower"; do
        IFS=: read -r ssh_target label <<< "$spec"
        LOG=$(ssh "$ssh_target" "head -2 /tmp/p2p_node.log" 2>/dev/null)
        echo "$LOG" | grep -q READY && ok "$label READY" || fail "$label not ready"
    done

    echo ""
    echo "3. Verify mesh"
    cd "$CORE_DIR"
    uv run python3 -c "
import asyncio, tempfile
from mascarade.p2p.asyncio_node import MascaradeP2PNode
async def main():
    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(listen_host='0.0.0.0', listen_port=4099, key_dir=d,
            bootstrap_peers=[('QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S', '$VM_HOST', 4001)])
        await node.start()
        await asyncio.sleep(6)
        caps = node.capabilities.all_capabilities()
        for pid, c in caps.items():
            print(f'  {c.label}: {c.capabilities} ({c.role})')
        await node.stop()
        print(f'MESH_OK:{len(caps)}')
asyncio.run(main())
" 2>&1 | while read -r line; do
        if [[ "$line" == MESH_OK:* ]]; then
            count="${line#MESH_OK:}"
            ok "Mesh: $count peers visible"
        else
            echo "$line"
        fi
    done
}

# ───────────────────────────────────────────
cmd_stop() {
    echo "=== Stopping P2P Mesh ==="
    ssh root@$VM_HOST "pkill -f node_start_bootstrap 2>/dev/null" && ok "VM stopped" || info "VM already stopped"
    ssh cils@$CILS_HOST "pkill -f task_handler_worker 2>/dev/null" && ok "CILS stopped" || info "CILS already stopped"
    ssh clems@$TOWER_HOST "pkill -f task_handler_worker 2>/dev/null" && ok "Tower stopped" || info "Tower already stopped"
    ssh kxkm@$KXKM_HOST "pkill -f node_start_worker 2>/dev/null" 2>/dev/null && ok "KXKM stopped" || info "KXKM already stopped"
}

# ───────────────────────────────────────────
cmd_status() {
    echo "=== P2P Mesh Status ==="
    for spec in "root@$VM_HOST:VM" "cils@$CILS_HOST:CILS" "clems@$TOWER_HOST:Tower" "kxkm@$KXKM_HOST:KXKM"; do
        IFS=: read -r ssh_target label <<< "$spec"
        PID=$(ssh "$ssh_target" "lsof -ti:4001 2>/dev/null" 2>/dev/null)
        if [ -n "$PID" ]; then
            ok "$label: running (PID $PID)"
        else
            fail "$label: not running"
        fi
    done
}

# ───────────────────────────────────────────
cmd_test() {
    echo "=== Task Distribution Test ==="
    cd "$CORE_DIR"
    uv run python3 -c "
import asyncio, tempfile, json
from mascarade.p2p.asyncio_node import MascaradeP2PNode

async def main():
    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(listen_host='0.0.0.0', listen_port=4098, key_dir=d,
            bootstrap_peers=[('QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S', '$VM_HOST', 4001)])
        await node.start()
        await asyncio.sleep(6)

        tests = [
            ('compute', {'action': 'ping'}),
            ('kicad-validation', {'action': 'echo', 'message': 'validate'}),
            ('storage', {'action': 'echo', 'message': 'store'}),
        ]
        for cap, payload in tests:
            try:
                r = await node.distribute_task(payload=payload, capability=cap, timeout=10)
                print(f'OK|{cap}|{r.result}')
            except Exception as e:
                print(f'FAIL|{cap}|{e}')
        await node.stop()

asyncio.run(main())
" 2>&1 | while read -r line; do
        if [[ "$line" == OK\|* ]]; then
            cap=$(echo "$line" | cut -d'|' -f2)
            result=$(echo "$line" | cut -d'|' -f3-)
            ok "$cap → $result"
        elif [[ "$line" == FAIL\|* ]]; then
            cap=$(echo "$line" | cut -d'|' -f2)
            err=$(echo "$line" | cut -d'|' -f3-)
            fail "$cap → $err"
        fi
    done
}

# ───────────────────────────────────────────
cmd_inference() {
    echo "=== Inference Test ==="
    cd "$CORE_DIR"

    # Start local server
    info "Starting mascarade server..."
    uv run python -m uvicorn mascarade.server:app --host 127.0.0.1 --port 8100 > /tmp/mascarade_server.log 2>&1 &
    SERVER_PID=$!
    sleep 4

    # Health
    HEALTH=$(curl -s http://127.0.0.1:8100/health 2>/dev/null)
    echo "$HEALTH" | grep -q '"ok"' && ok "Server healthy" || fail "Server not healthy"

    # /send
    SEND=$(curl -s -X POST http://127.0.0.1:8100/send -H 'Content-Type: application/json' \
        -d '{"messages":[{"role":"user","content":"dis pong"}]}' 2>/dev/null)
    echo "$SEND" | grep -qi "pong" && ok "/send → pong" || fail "/send failed"

    # /v1/chat/completions
    COMPAT=$(curl -s -X POST http://127.0.0.1:8100/v1/chat/completions -H 'Content-Type: application/json' \
        -d '{"model":"claude-sonnet-4-6","messages":[{"role":"user","content":"dis pong"}]}' 2>/dev/null)
    echo "$COMPAT" | grep -qi "pong" && ok "/v1/chat/completions → pong" || fail "/v1/chat/completions failed"

    kill $SERVER_PID 2>/dev/null
    ok "Server stopped"
}

# ───────────────────────────────────────────
cmd_full() {
    cmd_start
    echo ""
    cmd_test
    echo ""
    cmd_inference
    echo ""
    echo "=== All done ==="
}

# ───────────────────────────────────────────
case "${1:-full}" in
    start)     cmd_start ;;
    stop)      cmd_stop ;;
    status)    cmd_status ;;
    test)      cmd_test ;;
    inference) cmd_inference ;;
    full)      cmd_full ;;
    *)         echo "Usage: $0 {start|stop|status|test|inference|full}" ;;
esac
