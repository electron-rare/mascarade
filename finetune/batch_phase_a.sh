#!/bin/bash
# Phase A — SFT Training (Smart Strategy)
# 3 epochs on small domains (<10K), 1 epoch on large domains (>10K)
# Sequential execution on RTX 4090
# Run label: tuning-party-hf

set -e
cd /ai/saisail/mascarade/finetune
source /ai/saisail/mascarade/venv_tuning/bin/activate

LABEL="tuning-party-hf"
SEQ_LEN=1024

echo "=========================================="
echo "Phase A — SFT Training (Smart Strategy)"
echo "Start: $(date)"
echo "=========================================="

# Small domains — 3 epochs
for domain in stm32 freecad iot dsp kicad emc platformio; do
  echo ""
  echo ">>> Training $domain (3 epochs) — $(date)"
  python run_local.py $domain \
    --device gpu --run-label $LABEL \
    --seq-len $SEQ_LEN --epochs 3 --eval --verbose \
    2>&1 | tee "runs/${LABEL}_${domain}_$(date +%Y%m%d_%H%M%S).log"
  echo ">>> Done $domain — $(date)"
done

# Large domains — 1 epoch
for domain in embedded power; do
  echo ""
  echo ">>> Training $domain (1 epoch) — $(date)"
  python run_local.py $domain \
    --device gpu --run-label $LABEL \
    --seq-len $SEQ_LEN --epochs 1 --eval --verbose \
    2>&1 | tee "runs/${LABEL}_${domain}_$(date +%Y%m%d_%H%M%S).log"
  echo ">>> Done $domain — $(date)"
done

# Spice — 1 epoch, capped at 20K samples
echo ""
echo ">>> Training spice (1 epoch, max 20K) — $(date)"
python run_local.py spice \
  --device gpu --run-label $LABEL \
  --seq-len $SEQ_LEN --epochs 1 --max-samples 20000 --eval --verbose \
  2>&1 | tee "runs/${LABEL}_spice_$(date +%Y%m%d_%H%M%S).log"
echo ">>> Done spice — $(date)"

echo ""
echo "=========================================="
echo "Phase A COMPLETE — $(date)"
echo "=========================================="
