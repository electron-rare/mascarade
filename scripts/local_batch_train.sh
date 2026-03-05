#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# local_batch_train.sh - Train all 3 domains sequentially on local GPU
#
# Usage:
#   ./scripts/local_batch_train.sh              # all 3 domains
#   ./scripts/local_batch_train.sh stm32 kicad  # specific domains
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

DOMAINS=("${@:-stm32 kicad generic}")
if [ $# -eq 0 ]; then
    DOMAINS=(stm32 kicad generic)
fi

VENV="$SCRIPT_DIR/venv_tuning/bin/activate"
LOG_DIR="$SCRIPT_DIR/fine_tuned_models/logs"
mkdir -p "$LOG_DIR"

STARTED=$(date '+%Y-%m-%d %H:%M:%S')

echo "============================================================"
echo " LOCAL BATCH TRAINING - $(date)"
echo " Domains: ${DOMAINS[*]}"
echo " Model: GPT-2 124M (ultrasmall)"
echo " GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'unknown')"
echo "============================================================"

source "$VENV"

RESULTS=()

for DOMAIN in "${DOMAINS[@]}"; do
    DATASET="$SCRIPT_DIR/datasets/${DOMAIN}_dataset.txt"
    LOG="$LOG_DIR/${DOMAIN}_$(date '+%Y%m%d_%H%M%S').log"

    echo ""
    echo "============================================================"
    echo " [$DOMAIN] Starting at $(date '+%H:%M:%S')"
    echo " Dataset: $DATASET"
    echo " Log: $LOG"
    echo "============================================================"

    if [ ! -f "$DATASET" ]; then
        echo " SKIP: dataset not found"
        RESULTS+=("$DOMAIN: SKIPPED (no dataset)")
        continue
    fi

    START_TIME=$(date +%s)

    if python fine_tuning_base.py \
        --domain "$DOMAIN" \
        --train \
        --ultrasmall \
        --short-seq \
        --dataset "$DATASET" \
        --epochs 3 \
        2>&1 | tee "$LOG"; then
        STATUS="OK"
    else
        STATUS="FAILED"
    fi

    END_TIME=$(date +%s)
    DURATION=$(( (END_TIME - START_TIME) / 60 ))

    RESULTS+=("$DOMAIN: $STATUS (${DURATION}min)")
    echo ""
    echo " [$DOMAIN] $STATUS in ${DURATION} minutes"

    # Clear GPU cache between runs
    python -c "import torch; torch.cuda.empty_cache()" 2>/dev/null || true
done

FINISHED=$(date '+%Y-%m-%d %H:%M:%S')

echo ""
echo "============================================================"
echo " BATCH TRAINING COMPLETE"
echo " Started:  $STARTED"
echo " Finished: $FINISHED"
echo "============================================================"
for R in "${RESULTS[@]}"; do
    echo "  $R"
done
echo "============================================================"
echo ""
echo "Models saved in: $SCRIPT_DIR/fine_tuned_models/"
echo "Logs saved in:   $LOG_DIR/"
