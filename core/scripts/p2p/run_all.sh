#!/usr/bin/env bash
# run_all.sh — Start full P2P mesh + mascarade server
# Usage: ./run_all.sh [start|stop|status|test|research|inference|full]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

VM_HOST="192.168.0.119"
VM_PORT="4002"
CILS_HOST="192.168.0.210"
TOWER_HOST="192.168.0.120"
KXKM_HOST="kxkm-ai"
LOCAL_BRIDGE_PORT="${LOCAL_BRIDGE_PORT:-4001}"
BOOTSTRAP_ID="QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S"
RESEARCH_TIMEOUT_SECONDS="${RESEARCH_TIMEOUT_SECONDS:-60}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${YELLOW}→${NC} $1"; }

local_mesh_pid() {
    local pid=""
    pid="$(lsof -ti:$LOCAL_BRIDGE_PORT 2>/dev/null | head -1 || true)"
    if [[ -n "$pid" ]] && ps -p "$pid" -o command= | grep -Eq "node_start_bridge.py|task_handler_worker.py"; then
        echo "$pid"
    fi
}

# ───────────────────────────────────────────
cmd_start() {
    echo "=== Starting P2P Mesh ==="

    echo ""
    echo "1. VM Bootstrap + Relay"
    ssh root@$VM_HOST "pkill -f '[n]ode_start_bootstrap.py' 2>/dev/null || true; pkill -f '[t]ask_handler_worker.py' 2>/dev/null || true; sleep 1; cd /mascarade/core && P2P_LISTEN_PORT=$VM_PORT nohup python3 scripts/p2p/node_start_bootstrap.py </dev/null >/tmp/p2p_node.log 2>&1 &" >/dev/null 2>&1 || true
    sleep 3
    VM_LOG=$(ssh root@$VM_HOST "head -2 /tmp/p2p_node.log" 2>/dev/null || true)
    echo "$VM_LOG" | grep -q READY && ok "VM READY" || fail "VM not ready: $VM_LOG"

    echo ""
    echo "2. Local bridge"
    BRIDGE_PY="$CORE_DIR/.venv/bin/python"
    [[ -x "$BRIDGE_PY" ]] || BRIDGE_PY="python3"
    existing_bridge_pid="$(local_mesh_pid || true)"
    if [[ -n "$existing_bridge_pid" ]]; then
        kill "$existing_bridge_pid" 2>/dev/null || true
        sleep 1
    fi
    (
        cd "$CORE_DIR"
        P2P_BOOTSTRAP_PORT="$VM_PORT" \
        P2P_LISTEN_PORT="$LOCAL_BRIDGE_PORT" \
        nohup "$BRIDGE_PY" scripts/p2p/node_start_bridge.py </dev/null >/tmp/p2p_bridge.log 2>&1 &
    ) && ok "GrosMac bridge started" || fail "GrosMac bridge start failed"
    sleep 3
    BRIDGE_LOG="$(head -2 /tmp/p2p_bridge.log 2>/dev/null || true)"
    if [[ -n "$(local_mesh_pid || true)" ]]; then
        ok "GrosMac bridge READY"
    else
        fail "GrosMac bridge not ready: $BRIDGE_LOG"
    fi

    echo ""
    echo "3. Workers"
    for spec in "cils@$CILS_HOST:CILS MacBook:compute,ft-validation" "clems@$TOWER_HOST:Tower:compute,storage,ft-archive"; do
        IFS=: read -r ssh_target label caps <<< "$spec"
        ssh "$ssh_target" "pkill -f '[t]ask_handler_worker.py' 2>/dev/null || true; for pid in \$(lsof -ti:4001 2>/dev/null || true); do kill \"\$pid\" 2>/dev/null || true; done; sleep 1; pkill -9 -f '[t]ask_handler_worker.py' 2>/dev/null || true; for pid in \$(lsof -ti:4001 2>/dev/null || true); do kill -9 \"\$pid\" 2>/dev/null || true; done; sleep 1; cd ~/mascarade/core && P2P_BOOTSTRAP_PORT=$VM_PORT P2P_CAPABILITIES=$caps P2P_LABEL='$label' nohup .venv/bin/python scripts/p2p/task_handler_worker.py </dev/null >/tmp/p2p_node.log 2>&1 & exit 0" >/dev/null 2>&1 || true
    done
    sleep 4

    for spec in "cils@$CILS_HOST:CILS" "clems@$TOWER_HOST:Tower"; do
        IFS=: read -r ssh_target label <<< "$spec"
        LOG=$(ssh "$ssh_target" "head -2 /tmp/p2p_node.log" 2>/dev/null)
        echo "$LOG" | grep -q READY && ok "$label READY" || fail "$label not ready"
    done

    echo ""
    echo "4. Verify mesh"
    cd "$CORE_DIR"
    uv run python3 -c "
import asyncio, tempfile
from mascarade.p2p.asyncio_node import MascaradeP2PNode
async def main():
    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(listen_host='0.0.0.0', listen_port=4099, key_dir=d,
            bootstrap_peers=[('$BOOTSTRAP_ID', '$VM_HOST', $VM_PORT)])
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
    existing_bridge_pid="$(local_mesh_pid || true)"
    if [[ -n "$existing_bridge_pid" ]]; then
        kill "$existing_bridge_pid" 2>/dev/null && ok "GrosMac bridge stopped" || info "GrosMac bridge already stopped"
    else
        info "GrosMac bridge already stopped"
    fi
    ssh cils@$CILS_HOST "pkill -f task_handler_worker 2>/dev/null" && ok "CILS stopped" || info "CILS already stopped"
    ssh clems@$TOWER_HOST "pkill -f task_handler_worker 2>/dev/null" && ok "Tower stopped" || info "Tower already stopped"
    ssh kxkm@$KXKM_HOST "pkill -f node_start_worker 2>/dev/null" 2>/dev/null && ok "KXKM stopped" || info "KXKM already stopped"
}

# ───────────────────────────────────────────
cmd_status() {
    echo "=== P2P Mesh Status ==="
    if [[ -n "$(local_mesh_pid || true)" ]]; then
        ok "GrosMac local node: listening on :$LOCAL_BRIDGE_PORT"
    else
        fail "GrosMac local node: not running on :$LOCAL_BRIDGE_PORT"
    fi
    for spec in "root@$VM_HOST:VM:$VM_PORT" "cils@$CILS_HOST:CILS:4001" "clems@$TOWER_HOST:Tower:4001" "kxkm@$KXKM_HOST:KXKM:4001"; do
        IFS=: read -r ssh_target label port <<< "$spec"
        LISTENING=$(ssh -o ConnectTimeout=5 "$ssh_target" "lsof -ti:$port 2>/dev/null || ss -tlnp 2>/dev/null | grep -o ':${port}[[:space:]]' | head -1" 2>/dev/null)
        if [ -n "$LISTENING" ]; then
            ok "$label: listening on :$port"
        else
            fail "$label: not running on :$port"
        fi
    done
}

# ───────────────────────────────────────────
cmd_test() {
    echo "=== Task Distribution Test ==="
    cd "$CORE_DIR"
    local failures=0
    local producer_rc=0
    while read -r line; do
        if [[ "$line" == OK\|* ]]; then
            cap=$(echo "$line" | cut -d'|' -f2)
            result=$(echo "$line" | cut -d'|' -f3)
            claimer=$(echo "$line" | cut -d'|' -f4)
            ok "$cap → $result (claimed_by=${claimer})"
        elif [[ "$line" == FAIL\|* ]]; then
            cap=$(echo "$line" | cut -d'|' -f2)
            status=$(echo "$line" | cut -d'|' -f3)
            err=$(echo "$line" | cut -d'|' -f4)
            claimer=$(echo "$line" | cut -d'|' -f5)
            fail "$cap → status=${status} error=${err} claimed_by=${claimer}"
            failures=1
        elif [[ "$line" == WARN\|stop\|timeout ]]; then
            warn "Temporary audit node stop timed out after results were collected"
        elif [[ "$line" == EXIT\|* ]]; then
            producer_rc=$(echo "$line" | cut -d'|' -f2)
        fi
    done < <(
        uv run python3 -u -c "
import asyncio, tempfile, json
from mascarade.p2p.asyncio_node import MascaradeP2PNode

async def main():
    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(listen_host='0.0.0.0', listen_port=4098, key_dir=d,
            bootstrap_peers=[('$BOOTSTRAP_ID', '$VM_HOST', $VM_PORT)])
        await node.start()
        await asyncio.sleep(6)

        tests = [
            ('compute', {'action': 'ping'}),
            ('ft-validation', {'action': 'echo', 'message': 'validate'}),
            ('storage', {'action': 'echo', 'message': 'store'}),
        ]
        for cap, payload in tests:
            r = await node.distribute_task(payload=payload, capability=cap, timeout=10)
            if r.status.value == 'completed' and r.result is not None:
                print(f'OK|{cap}|{json.dumps(r.result)}|{r.claimed_by}', flush=True)
            else:
                error = r.error or ''
                claimed_by = r.claimed_by or ''
                print(f'FAIL|{cap}|{r.status.value}|{error}|{claimed_by}', flush=True)
        try:
            await asyncio.wait_for(node.stop(), timeout=5)
        except asyncio.TimeoutError:
            print('WARN|stop|timeout', flush=True)

asyncio.run(main())
" 2>&1
        printf 'EXIT|%s\n' "$?"
    )
    if [[ "$producer_rc" -ne 0 || "$failures" -ne 0 ]]; then
        return 1
    fi
}

# ───────────────────────────────────────────
cmd_research() {
    echo "=== Fine-tune Research Dispatch ==="
    if [[ -z "$(local_mesh_pid || true)" ]]; then
        fail "GrosMac local node not running on :$LOCAL_BRIDGE_PORT"
        return 1
    fi

    cd "$CORE_DIR"
    local failures=0
    local producer_rc=0
    while read -r line; do
        if [[ "$line" == PEERS\|* ]]; then
            peers=$(echo "$line" | cut -d'|' -f2-)
            info "ft-research peers → $peers"
        elif [[ "$line" == OK\|* ]]; then
            count=$(echo "$line" | cut -d'|' -f2)
            first=$(echo "$line" | cut -d'|' -f3)
            claimer=$(echo "$line" | cut -d'|' -f4)
            ok "ft-research → ${count} candidates, first=${first}, claimed_by=${claimer}"
        elif [[ "$line" == FAIL\|* ]]; then
            status=$(echo "$line" | cut -d'|' -f2)
            err=$(echo "$line" | cut -d'|' -f3)
            claimer=$(echo "$line" | cut -d'|' -f4)
            fail "ft-research → status=${status} error=${err} claimed_by=${claimer}"
            failures=1
        elif [[ "$line" == WARN\|stop\|timeout ]]; then
            warn "Temporary research node stop timed out after results were collected"
        elif [[ "$line" == EXIT\|* ]]; then
            producer_rc=$(echo "$line" | cut -d'|' -f2)
        fi
    done < <(
        uv run python3 -u -c "
import asyncio, tempfile, json
from mascarade.p2p.asyncio_node import MascaradeP2PNode

async def main():
    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(
            listen_host='0.0.0.0',
            listen_port=4097,
            key_dir=d,
            bootstrap_peers=[('$BOOTSTRAP_ID', '$VM_HOST', $VM_PORT)],
        )
        await node.start()
        await asyncio.sleep(6)

        peers = await node.find_capable_peers('ft-research')
        labels = [p.label or p.peer_id for p in peers]
        print(f'PEERS|{json.dumps(labels)}', flush=True)

        task = await node.distribute_task(
            payload={'action': 'search_models', 'task': 'code', 'max_size_gb': 4.0},
            capability='ft-research',
            timeout=$RESEARCH_TIMEOUT_SECONDS,
        )
        if task.status.value == 'completed' and task.result is not None:
            candidates = task.result.get('candidates', [])
            first = candidates[0]['model_id'] if candidates else ''
            print(f'OK|{len(candidates)}|{first}|{task.claimed_by}', flush=True)
        else:
            error = task.error or ''
            claimed_by = task.claimed_by or ''
            print(f'FAIL|{task.status.value}|{error}|{claimed_by}', flush=True)
        try:
            await asyncio.wait_for(node.stop(), timeout=5)
        except asyncio.TimeoutError:
            print('WARN|stop|timeout', flush=True)

asyncio.run(main())
" 2>&1
        printf 'EXIT|%s\n' "$?"
    )
    if [[ "$producer_rc" -ne 0 || "$failures" -ne 0 ]]; then
        return 1
    fi
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
    cmd_research
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
    research)  cmd_research ;;
    inference) cmd_inference ;;
    full)      cmd_full ;;
    *)         echo "Usage: $0 {start|stop|status|test|research|inference|full}" ;;
esac
