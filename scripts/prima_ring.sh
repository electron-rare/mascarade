#!/bin/bash
# prima_ring.sh — Launch a prima.cpp distributed ring cluster
#
# Usage:
#   ./scripts/prima_ring.sh start <model.gguf> [--nodes 2|3]
#   ./scripts/prima_ring.sh stop
#   ./scripts/prima_ring.sh status
#
# Ring topology:
#   2-node: KXKM-AI (rank 0, head) → Tower (rank 1) → back
#   3-node: KXKM-AI (rank 0, head) → Tower (rank 1) → GrosMac (rank 2) → back
#
# Prerequisites:
#   - prima.cpp built on all nodes (/tmp/prima-cpp/llama-cli)
#   - Model GGUF file present on all nodes (same path)
#   - SSH access configured (via Photon bridge for KXKM-AI)

set -euo pipefail

# ── Node configuration ─────────────────────────────────────────────
KXKM_AI_IP="100.87.54.119"    # Tailscale IP
TOWER_IP="192.168.0.120"      # LAN IP
GROSMAC_IP="100.80.178.42"    # Tailscale IP

KXKM_SSH="ssh cils@192.168.0.119 ssh kxkm@${KXKM_AI_IP}"
TOWER_SSH="ssh clems@tower"
GROSMAC_SSH="ssh cils@192.168.0.119 ssh electron@${GROSMAC_IP}"

PRIMA_BIN="/tmp/prima-cpp/llama-cli"
ZMQ_PORT=9000
CONTEXT=2048
GPU_LAYERS_KXKM=30   # RTX 4090 — most layers on GPU
GPU_LAYERS_TOWER=5    # P2000 — few GPU layers
GPU_LAYERS_GROSMAC=0  # M5 ANE — CPU/Metal only

# ── Functions ──────────────────────────────────────────────────────

start_ring() {
    local model="$1"
    local nodes="${2:-2}"

    echo "Starting prima.cpp ring cluster (${nodes} nodes)"
    echo "Model: ${model}"
    echo ""

    if [ "$nodes" -eq 2 ]; then
        echo "Ring: KXKM-AI (rank 0) → Tower (rank 1) → KXKM-AI"

        # Start worker first (Tower, rank 1)
        echo "[Tower] Starting worker (rank 1)..."
        $TOWER_SSH "nohup ${PRIMA_BIN} -m ${model} \
            --world 2 --rank 1 \
            --master ${KXKM_AI_IP} --next ${KXKM_AI_IP} \
            -ngl ${GPU_LAYERS_TOWER} -c ${CONTEXT} \
            > /tmp/prima-worker.log 2>&1 &" &

        sleep 2

        # Start head (KXKM-AI, rank 0)
        echo "[KXKM-AI] Starting head (rank 0)..."
        $KXKM_SSH "nohup ${PRIMA_BIN} -m ${model} \
            --world 2 --rank 0 \
            --master ${KXKM_AI_IP} --next ${TOWER_IP} \
            -ngl ${GPU_LAYERS_KXKM} -c ${CONTEXT} \
            -p 'Hello, I am a distributed LLM.' -n 32 \
            > /tmp/prima-head.log 2>&1 &"

    elif [ "$nodes" -eq 3 ]; then
        echo "Ring: KXKM-AI (rank 0) → Tower (rank 1) → GrosMac (rank 2) → KXKM-AI"

        # Start workers
        echo "[GrosMac] Starting worker (rank 2)..."
        $GROSMAC_SSH "nohup ${PRIMA_BIN} -m ${model} \
            --world 3 --rank 2 \
            --master ${KXKM_AI_IP} --next ${KXKM_AI_IP} \
            -ngl ${GPU_LAYERS_GROSMAC} -c ${CONTEXT} \
            > /tmp/prima-worker.log 2>&1 &" &

        echo "[Tower] Starting worker (rank 1)..."
        $TOWER_SSH "nohup ${PRIMA_BIN} -m ${model} \
            --world 3 --rank 1 \
            --master ${KXKM_AI_IP} --next ${GROSMAC_IP} \
            -ngl ${GPU_LAYERS_TOWER} -c ${CONTEXT} \
            > /tmp/prima-worker.log 2>&1 &" &

        sleep 3

        # Start head
        echo "[KXKM-AI] Starting head (rank 0)..."
        $KXKM_SSH "nohup ${PRIMA_BIN} -m ${model} \
            --world 3 --rank 0 \
            --master ${KXKM_AI_IP} --next ${TOWER_IP} \
            -ngl ${GPU_LAYERS_KXKM} -c ${CONTEXT} \
            -p 'Hello, I am a distributed LLM.' -n 32 \
            > /tmp/prima-head.log 2>&1 &"
    fi

    echo ""
    echo "Ring started. Check logs:"
    echo "  KXKM-AI: ssh ... cat /tmp/prima-head.log"
    echo "  Tower:   ssh clems@tower cat /tmp/prima-worker.log"
}

stop_ring() {
    echo "Stopping prima.cpp ring cluster..."
    $KXKM_SSH "pkill -f llama-cli 2>/dev/null; echo 'KXKM-AI stopped'" &
    $TOWER_SSH "pkill -f llama-cli 2>/dev/null; echo 'Tower stopped'" &
    $GROSMAC_SSH "pkill -f llama-cli 2>/dev/null; echo 'GrosMac stopped'" 2>/dev/null &
    wait
    echo "All nodes stopped."
}

status_ring() {
    echo "=== KXKM-AI ==="
    $KXKM_SSH "pgrep -la llama-cli 2>/dev/null || echo 'not running'" 2>&1
    echo "=== Tower ==="
    $TOWER_SSH "pgrep -la llama-cli 2>/dev/null || echo 'not running'" 2>&1
    echo "=== GrosMac ==="
    $GROSMAC_SSH "pgrep -la llama-cli 2>/dev/null || echo 'not running'" 2>/dev/null || echo "unreachable"
}

# ── Main ───────────────────────────────────────────────────────────

case "${1:-help}" in
    start)
        model="${2:?Usage: prima_ring.sh start <model.gguf> [--nodes N]}"
        nodes="${4:-2}"
        start_ring "$model" "$nodes"
        ;;
    stop)
        stop_ring
        ;;
    status)
        status_ring
        ;;
    *)
        echo "Usage: prima_ring.sh {start|stop|status}"
        echo "  start <model.gguf> [--nodes 2|3]"
        echo "  stop"
        echo "  status"
        ;;
esac
