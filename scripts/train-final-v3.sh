#!/usr/bin/env bash
set -euo pipefail
cd /ai/saisail/mascarade
source .venv-finetune/bin/activate
export WANDB_DISABLED=true TOKENIZERS_PARALLELISM=false

CLEAN="finetune/datasets/cleaned_final"
IMP="finetune/datasets/improved_final"

MODELS=(
    "mascarade-spice-v4|${IMP}/spice_improved.jsonl|spice"
    "mascarade-emc-v3|${CLEAN}/emc_final.jsonl|emc"
    "mascarade-power-v3|${CLEAN}/power_final.jsonl|power"
    "mascarade-dsp-v3|${CLEAN}/dsp_final.jsonl|dsp"
    "mascarade-ipc-v3|${CLEAN}/ipc_final.jsonl|ipc"
    "mascarade-kicad-v5|${CLEAN}/kicad-v3_final.jsonl|kicad"
    "mascarade-embedded-v4|${CLEAN}/embedded_final.jsonl|embedded"
    "mascarade-analog-v3|${CLEAN}/analog_final.jsonl|analog"
    "mascarade-freecad-v2|${CLEAN}/freecad_final.jsonl|freecad"
    "mascarade-platformio-v2|${CLEAN}/platformio_final.jsonl|platformio"
    "mascarade-missing-v3|${CLEAN}/missing_final.jsonl|missing"
    "mascarade-iot-v3|${CLEAN}/iot_final.jsonl|iot"
    "mascarade-stm32-v2|${CLEAN}/stm32_final.jsonl|stm32"
    "mascarade-verilog-v2|${CLEAN}/rtlcoder3_final.jsonl|verilog"
)

for entry in "${MODELS[@]}"; do
    IFS='|' read -r NAME DATASET DOMAIN <<< "$entry"
    [ ! -f "$DATASET" ] && echo "SKIP $NAME (no file)" && continue
    LINES=$(wc -l < "$DATASET")
    [ "$LINES" -lt 50 ] && echo "SKIP $NAME ($LINES too few)" && continue

    echo ""
    echo "============================================================"
    echo "TRAINING: $NAME ($LINES examples)"
    echo "============================================================"

    python3 -u scripts/train-single-model.py "$NAME" "$DATASET" "$DOMAIN" 2>&1
    echo "$NAME: exit $?"
    sleep 3
done
echo ""
echo "ALL DONE $(date)"
