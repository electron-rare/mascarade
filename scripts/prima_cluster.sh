#!/usr/bin/env bash
# Prima.cpp distributed cluster launcher
# Runs Qwen2.5-72B across KXKM-AI (GPU) + Tower (CPU) + CILS (CPU)
#
# Usage:
#   ./scripts/prima_cluster.sh start   # Launch all nodes
#   ./scripts/prima_cluster.sh stop    # Stop all nodes
#   ./scripts/prima_cluster.sh status  # Check cluster status
#   ./scripts/prima_cluster.sh test    # Run a test inference
#
set -euo pipefail

# Cluster config
MASTER="kxkm@kxkm-ai"
WORKER1="clems@192.168.0.120"
WORKER2="cils@192.168.0.210"

MASTER_PORT=8300
WORKER1_PORT=8301
WORKER2_PORT=8302

MODEL="/home/kxkm/.ollama/models/blobs/$(ssh -o ConnectTimeout=5 $MASTER '/usr/local/bin/ollama show qwen2.5:72b-instruct-q4_K_M --modelfile 2>/dev/null | grep "^FROM" | cut -d" " -f2 | xargs basename' 2>/dev/null || echo 'unknown')"

# GPU layers for KXKM-AI (RTX 4090 24GB → ~30 layers of 72B Q4)
GPU_LAYERS=35

cmd_start() {
    echo "=== Starting Prima.cpp distributed cluster ==="
    echo "Model: Qwen2.5-72B-Q4_K_M (47 GB)"
    echo "Master: KXKM-AI (RTX 4090, GPU layers 0-$GPU_LAYERS)"
    echo "Worker 1: Tower (CPU, 31GB RAM)"
    echo "Worker 2: CILS (CPU, 16GB RAM)"
    echo ""

    # First stop Ollama on KXKM-AI to free GPU
    echo "[1/4] Stopping Ollama on KXKM-AI..."
    ssh -o ConnectTimeout=10 $MASTER "pkill -f 'ollama runner' 2>/dev/null; sleep 2" || true

    # Start RPC workers on Tower and CILS
    echo "[2/4] Starting RPC worker on Tower:$WORKER1_PORT..."
    ssh -o ConnectTimeout=10 $WORKER1 "
        cd ~/prima.cpp && \
        export LD_LIBRARY_PATH=/home/clems/.local/lib:\$LD_LIBRARY_PATH && \
        nohup ./main --rpc-server --host 0.0.0.0 --port $WORKER1_PORT > /tmp/prima-worker.log 2>&1 &
        echo PID=\$!
    " || echo "WARNING: Tower worker failed to start"

    echo "[3/4] Starting RPC worker on CILS:$WORKER2_PORT..."
    ssh -o ConnectTimeout=10 $WORKER2 "
        cd ~/prima.cpp && \
        export DYLD_LIBRARY_PATH=/Users/cils/.local/lib:\$DYLD_LIBRARY_PATH && \
        nohup ./server --rpc-server --host 0.0.0.0 --port $WORKER2_PORT > /tmp/prima-worker.log 2>&1 &
        echo PID=\$!
    " || echo "WARNING: CILS worker failed to start"

    sleep 3

    # Start master on KXKM-AI with RPC peers
    echo "[4/4] Starting master on KXKM-AI:$MASTER_PORT..."
    ssh -o ConnectTimeout=10 $MASTER "
        cd ~/prima.cpp && \
        export LD_LIBRARY_PATH=/home/kxkm/.local/lib:\$LD_LIBRARY_PATH && \
        nohup ./llama-server \
            -m $MODEL \
            -ngl $GPU_LAYERS \
            -c 4096 \
            --host 0.0.0.0 \
            --port $MASTER_PORT \
            -t 14 \
            --rpc 192.168.0.120:$WORKER1_PORT,192.168.0.210:$WORKER2_PORT \
            > /tmp/prima-master.log 2>&1 &
        echo PID=\$!
    "

    echo ""
    echo "=== Cluster starting... wait 30s for model load ==="
    sleep 30
    cmd_status
}

cmd_stop() {
    echo "=== Stopping Prima.cpp cluster ==="
    ssh -o ConnectTimeout=5 $MASTER "pkill -f llama-server 2>/dev/null" || true
    ssh -o ConnectTimeout=5 $WORKER1 "pkill -f 'rpc-server\|prima' 2>/dev/null" || true
    ssh -o ConnectTimeout=5 $WORKER2 "pkill -f 'rpc-server\|prima' 2>/dev/null" || true
    echo "All nodes stopped."
}

cmd_status() {
    echo "=== Prima.cpp cluster status ==="
    echo -n "KXKM-AI (master:$MASTER_PORT): "
    ssh -o ConnectTimeout=5 $MASTER "curl -s http://localhost:$MASTER_PORT/health 2>/dev/null || echo 'DOWN'" || echo "UNREACHABLE"

    echo -n "Tower (worker:$WORKER1_PORT): "
    ssh -o ConnectTimeout=5 $WORKER1 "ss -tlnp 2>/dev/null | grep $WORKER1_PORT > /dev/null && echo 'UP' || echo 'DOWN'" || echo "UNREACHABLE"

    echo -n "CILS (worker:$WORKER2_PORT): "
    ssh -o ConnectTimeout=5 $WORKER2 "ss -tlnp 2>/dev/null | grep $WORKER2_PORT > /dev/null && echo 'UP' || echo 'DOWN'; lsof -i :$WORKER2_PORT > /dev/null 2>&1 && echo 'UP' || true" || echo "UNREACHABLE"

    echo ""
    echo -n "GPU: "
    ssh -o ConnectTimeout=5 $MASTER "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader" 2>/dev/null || echo "N/A"
}

cmd_test() {
    echo "=== Testing Prima.cpp inference (Qwen2.5-72B) ==="
    echo "Query: What is the capital of France? Reply in one sentence."
    echo ""
    time curl -s "http://kxkm-ai:$MASTER_PORT/v1/chat/completions" \
        -H 'Content-Type: application/json' \
        -d '{
            "model": "qwen2.5-72b",
            "messages": [{"role": "user", "content": "What is the capital of France? Reply in one sentence."}],
            "max_tokens": 50,
            "temperature": 0.1
        }' | python3 -m json.tool 2>/dev/null
}

case "${1:-help}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    status) cmd_status ;;
    test) cmd_test ;;
    *) echo "Usage: $0 {start|stop|status|test}" ;;
esac
