#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# vast_finetune.sh - Automated Vast.ai fine-tuning workflow
#
# Rents cheapest RTX 3090, uploads data, trains, downloads results, destroys instance.
#
# Prerequisites:
#   pip install vastai
#   vastai set api-key YOUR_API_KEY
#
# Usage:
#   ./scripts/vast_finetune.sh                      # defaults: stm32, 1000 samples
#   ./scripts/vast_finetune.sh --domain kicad
#   ./scripts/vast_finetune.sh --domain generic --gpu A100
# ============================================================

DOMAIN="${DOMAIN:-stm32}"
GPU="${GPU:-RTX_3090}"
DISK_GB=50
DOCKER_IMAGE="pytorch/pytorch:2.2.0-cuda12.1-cudnn8-devel"
POLL_INTERVAL=15
TRAINING_TIMEOUT=14400  # 4h max
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain) DOMAIN="$2"; shift 2 ;;
        --gpu) GPU="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

DATASET_FILE="$SCRIPT_DIR/datasets/${DOMAIN}_dataset.txt"
if [ ! -f "$DATASET_FILE" ]; then
    echo "Dataset not found: $DATASET_FILE"
    echo "Run first: python download_datasets.py --domain $DOMAIN"
    exit 1
fi

echo "============================================================"
echo " VAST.AI FINE-TUNING - $DOMAIN on $GPU"
echo "============================================================"
echo " Dataset: $DATASET_FILE ($(du -h "$DATASET_FILE" | cut -f1))"
echo "============================================================"

# -- 1. Find cheapest offer --
echo ""
echo "[1/7] Searching for $GPU offers..."

GPU_FILTER="verified=true gpu_name=${GPU} num_gpus=1 gpu_ram>=24 cuda_max_good>=12.1 inet_down>=200 reliability>0.95"
OFFER_ID=$(vastai search offers "$GPU_FILTER" -o 'dph+' --raw | python3 -c "
import json, sys
offers = json.load(sys.stdin)
if not offers:
    sys.exit(1)
o = offers[0]
print(o['id'])
sys.stderr.write(f\"  {o['gpu_name']} | \${o['dph_total']:.3f}/hr | {o['gpu_ram']:.0f}GB VRAM\n\")
" 2>&1) || { echo "No offers found for $GPU. Try --gpu A100 or RTX_4090"; exit 1; }

# Extract just the ID (first line)
OFFER_ID=$(echo "$OFFER_ID" | head -1)
echo "  Selected offer: $OFFER_ID"

# -- 2. Create instance --
echo ""
echo "[2/7] Creating instance..."

SETUP_CMD="pip install -q transformers==4.57.6 peft==0.18.1 accelerate==1.12.0 bitsandbytes==0.43.2 datasets trl"

CREATE_RESULT=$(vastai create instance "$OFFER_ID" \
    --image "$DOCKER_IMAGE" \
    --disk "$DISK_GB" \
    --ssh \
    --direct \
    --onstart-cmd "$SETUP_CMD" \
    --raw)

INSTANCE_ID=$(echo "$CREATE_RESULT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('new_contract', ''))
")

echo "  Instance ID: $INSTANCE_ID"

# -- 3. Wait for running --
echo ""
echo "[3/7] Waiting for instance to start..."
for i in $(seq 1 60); do
    STATUS=$(vastai show instances --raw | python3 -c "
import json, sys
for inst in json.load(sys.stdin):
    if str(inst['id']) == '$INSTANCE_ID':
        print(inst.get('actual_status', 'loading'))
        break
" 2>/dev/null || echo "loading")
    echo "  [$i] Status: $STATUS"
    if [ "$STATUS" = "running" ]; then
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "  Timeout waiting for instance. Destroying..."
        vastai destroy instance "$INSTANCE_ID"
        exit 1
    fi
    sleep "$POLL_INTERVAL"
done

# -- 4. Get SSH info --
echo ""
echo "[4/7] Getting SSH connection..."

SSH_INFO=$(vastai show instances --raw | python3 -c "
import json, sys
for inst in json.load(sys.stdin):
    if str(inst['id']) == '$INSTANCE_ID':
        print(inst.get('ssh_host', ''), inst.get('ssh_port', ''))
        break
")
SSH_HOST=$(echo "$SSH_INFO" | awk '{print $1}')
SSH_PORT=$(echo "$SSH_INFO" | awk '{print $2}')

echo "  SSH: root@${SSH_HOST} -p ${SSH_PORT}"

# Wait for SSH availability
echo "  Waiting for SSH..."
for i in $(seq 1 30); do
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p "$SSH_PORT" root@"$SSH_HOST" "echo ok" 2>/dev/null; then
        break
    fi
    sleep 10
done

SSH_CMD="ssh -o StrictHostKeyChecking=no -p $SSH_PORT root@$SSH_HOST"
SCP_CMD="scp -o StrictHostKeyChecking=no -P $SSH_PORT"

# -- 5. Upload dataset + training script --
echo ""
echo "[5/7] Uploading files..."

$SCP_CMD "$DATASET_FILE" root@"$SSH_HOST":/workspace/dataset.txt
$SCP_CMD "$SCRIPT_DIR/scripts/vast_train_remote.py" root@"$SSH_HOST":/workspace/train.py

echo "  Uploaded dataset + train script"

# -- 6. Run training --
echo ""
echo "[6/7] Training... (this can take a while)"

$SSH_CMD "cd /workspace && python train.py \
    --domain $DOMAIN \
    --dataset /workspace/dataset.txt \
    --output-dir /workspace/output \
    2>&1 | tee train.log; touch /workspace/.done"

echo "  Training finished."

# -- 7. Download results + destroy --
echo ""
echo "[7/7] Downloading results..."

LOCAL_OUTPUT="$SCRIPT_DIR/fine_tuned_models/${DOMAIN}_vast"
mkdir -p "$LOCAL_OUTPUT"

$SCP_CMD -r root@"$SSH_HOST":/workspace/output/ "$LOCAL_OUTPUT"/
$SCP_CMD root@"$SSH_HOST":/workspace/train.log "$LOCAL_OUTPUT"/

echo "  Results saved to $LOCAL_OUTPUT"

echo ""
echo "Destroying instance $INSTANCE_ID..."
vastai destroy instance "$INSTANCE_ID"

echo ""
echo "============================================================"
echo " DONE - Fine-tuned model: $LOCAL_OUTPUT/final/"
echo "============================================================"
echo ""
echo "To use with Mascarade:"
echo "  python fine_tuning_base.py --domain $DOMAIN --evaluate --model-path $LOCAL_OUTPUT/final"
