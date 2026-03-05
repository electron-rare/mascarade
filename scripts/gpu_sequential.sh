#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# gpu_sequential.sh - Wait for STM32 GPU job, then run KiCad + Generic
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"
source "$SCRIPT_DIR/venv_tuning/bin/activate"

LOG_DIR="$SCRIPT_DIR/fine_tuned_models/logs"

echo "[$(date '+%H:%M:%S')] Waiting for STM32 GPU job (PID 551955) to finish..."

# Wait for the running STM32 GPU job
while kill -0 551955 2>/dev/null; do
    sleep 60
done

echo "[$(date '+%H:%M:%S')] STM32 GPU done. Clearing GPU cache..."
python -c "import torch; torch.cuda.empty_cache()" 2>/dev/null || true
sleep 5

# --- KiCad ---
echo ""
echo "============================================================"
echo "[$(date '+%H:%M:%S')] Starting KiCad on GPU (3 epochs)"
echo "============================================================"

python fine_tuning_base.py \
    --domain kicad --train --ultrasmall --short-seq \
    --dataset ./datasets/kicad_dataset.txt \
    --epochs 3 \
    --output-dir ./fine_tuned_models/kicad_gpu_e3 \
    2>&1 | tee "$LOG_DIR/kicad_gpu_e3.log"

echo "[$(date '+%H:%M:%S')] KiCad done."
python -c "import torch; torch.cuda.empty_cache()" 2>/dev/null || true
sleep 5

# --- Generic ---
echo ""
echo "============================================================"
echo "[$(date '+%H:%M:%S')] Starting Generic on GPU (3 epochs)"
echo "============================================================"

python fine_tuning_base.py \
    --domain generic --train --ultrasmall --short-seq \
    --dataset ./datasets/generic_dataset.txt \
    --epochs 3 \
    --output-dir ./fine_tuned_models/generic_gpu_e3 \
    2>&1 | tee "$LOG_DIR/generic_gpu_e3.log"

echo ""
echo "============================================================"
echo "[$(date '+%H:%M:%S')] ALL 3 DOMAINS COMPLETE"
echo "============================================================"
echo "Models:"
ls -d "$SCRIPT_DIR"/fine_tuned_models/*/final 2>/dev/null || echo "  Check logs for errors"
