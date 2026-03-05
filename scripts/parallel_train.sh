#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# parallel_train.sh - 1 GPU job + 10 CPU jobs in parallel
#
# Each job gets its own output dir under fine_tuned_models/
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/venv_tuning/bin/activate"

LOG_DIR="$SCRIPT_DIR/fine_tuned_models/logs"
mkdir -p "$LOG_DIR"

# 12 cores / 11 jobs ≈ 1 thread each for CPU, keep some headroom
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

echo "============================================================"
echo " PARALLEL TRAINING - $(date)"
echo " 1 GPU job + 10 CPU jobs"
echo " GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)"
echo " CPU cores: $(nproc)"
echo "============================================================"

PIDS=()
NAMES=()

launch() {
    local NAME=$1 DEVICE=$2 DOMAIN=$3 EPOCHS=$4 SIZE_FLAG=$5
    local LOG="$LOG_DIR/${NAME}.log"
    local OUT_DIR="$SCRIPT_DIR/fine_tuned_models/$NAME"
    local ENV_PREFIX=""

    if [ "$DEVICE" = "cpu" ]; then
        ENV_PREFIX="CUDA_VISIBLE_DEVICES="
    else
        ENV_PREFIX="CUDA_VISIBLE_DEVICES=0"
    fi

    mkdir -p "$OUT_DIR"
    echo "[$(date '+%H:%M:%S')] $NAME → $DEVICE (${DOMAIN}, ${EPOCHS}ep, ${SIZE_FLAG})"

    env $ENV_PREFIX python fine_tuning_base.py \
        --domain "$DOMAIN" --train $SIZE_FLAG --short-seq \
        --dataset "./datasets/${DOMAIN}_dataset.txt" \
        --epochs "$EPOCHS" \
        --output-dir "$OUT_DIR" \
        > "$LOG" 2>&1 &

    PIDS+=($!)
    NAMES+=("$NAME|$DEVICE|$LOG")
}

# ============================================================
# GPU JOB (1) - gets the full GPU
# ============================================================
launch "stm32_gpu_e3"        gpu  stm32   3  "--ultrasmall"

# ============================================================
# CPU JOBS (10) - spread across 12 cores
# ============================================================

# STM32 variants
launch "stm32_cpu_e1"        cpu  stm32   1  "--ultrasmall"
launch "stm32_cpu_e5"        cpu  stm32   5  "--ultrasmall"

# KiCad variants
launch "kicad_cpu_e1"        cpu  kicad   1  "--ultrasmall"
launch "kicad_cpu_e3"        cpu  kicad   3  "--ultrasmall"
launch "kicad_cpu_e5"        cpu  kicad   5  "--ultrasmall"

# Generic variants
launch "generic_cpu_e1"      cpu  generic 1  "--ultrasmall"
launch "generic_cpu_e3"      cpu  generic 3  "--ultrasmall"
launch "generic_cpu_e5"      cpu  generic 5  "--ultrasmall"

# Higher LoRA rank experiments (still ultrasmall GPT-2)
launch "stm32_cpu_e3_r16"    cpu  stm32   3  "--ultrasmall"
launch "kicad_cpu_e3_r16"    cpu  kicad   3  "--ultrasmall"

echo ""
echo "============================================================"
echo " ${#PIDS[@]} jobs launched (1 GPU + 10 CPU)"
echo ""
echo " Monitor all:    tail -f $LOG_DIR/*.log"
echo " Monitor GPU:    tail -f $LOG_DIR/stm32_gpu_e3.log"
echo " GPU usage:      nvidia-smi"
echo " CPU usage:      htop"
echo "============================================================"
echo ""

# --- Wait for all ---
FAIL=0
DONE=0
TOTAL=${#PIDS[@]}

for i in "${!PIDS[@]}"; do
    IFS='|' read -r NAME DEVICE LOG <<< "${NAMES[$i]}"
    if wait "${PIDS[$i]}"; then
        DONE=$((DONE + 1))
        echo "[$(date '+%H:%M:%S')] ($DONE/$TOTAL) DONE: $NAME ($DEVICE)"
    else
        DONE=$((DONE + 1))
        echo "[$(date '+%H:%M:%S')] ($DONE/$TOTAL) FAIL: $NAME → $LOG"
        FAIL=1
    fi
done

echo ""
echo "============================================================"
echo " ALL $TOTAL JOBS FINISHED - $(date)"
echo "============================================================"

# Summary
for i in "${!NAMES[@]}"; do
    IFS='|' read -r NAME DEVICE LOG <<< "${NAMES[$i]}"
    STATUS="?"
    grep -q "Training completed\|training_loss" "$LOG" 2>/dev/null && STATUS="OK"
    grep -q "Failed\|Error\|Traceback" "$LOG" 2>/dev/null && STATUS="FAIL"
    LOSS=$(grep -oP "train_loss.*?(\d+\.\d+)" "$LOG" 2>/dev/null | tail -1 | grep -oP "\d+\.\d+" || echo "N/A")
    printf "  %-25s %-5s %-6s loss=%s\n" "$NAME" "$DEVICE" "$STATUS" "$LOSS"
done

echo ""
echo " Models: $SCRIPT_DIR/fine_tuned_models/*/"
echo " Logs:   $LOG_DIR/"
echo "============================================================"

exit $FAIL
