#!/usr/bin/env bash
# Full pipeline: wait for queue -> benchmark v3 -> ML router -> RLVR
set -euo pipefail
cd /ai/saisail/mascarade
source .venv-finetune/bin/activate

echo "=== WAITING FOR TRAINING QUEUE ==="
while tmux has-session -t train-queue 2>/dev/null || tmux has-session -t train-spice 2>/dev/null; do
    echo "$(date +%H:%M) — queue still running..."
    sleep 120
done
echo "Queue finished!"

echo "=== BENCHMARK v3 ==="
python3 -u scripts/benchmark-v3-all-models.py 2>&1 | tee /tmp/benchmark-v3.log

echo "=== TRAIN ML ROUTER ==="
python3 -u scripts/train-ml-router.py 2>&1 | tee /tmp/ml-router.log

echo "=== RLVR KICAD DRC ==="
python3 -u scripts/train-rlvr-kicad.py 2>&1 | tee /tmp/rlvr-kicad.log

echo "=== ALL DONE ==="
date
