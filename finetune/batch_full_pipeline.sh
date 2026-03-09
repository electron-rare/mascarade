#!/bin/bash
# Full Pipeline — Phase A → merge/deploy → Phase B → Phase C
# Chains all training phases automatically on RTX 4090
# Each phase checks success of previous phase before continuing
#
# Usage:
#   bash batch_full_pipeline.sh                    # Full pipeline from scratch
#   bash batch_full_pipeline.sh --skip-phase-a     # Skip SFT (already done)
#   bash batch_full_pipeline.sh --only-phase-b     # Only rejection sampling
#   bash batch_full_pipeline.sh --only-phase-c     # Only DPO training

set -euo pipefail
cd /ai/saisail/mascarade/finetune
source /ai/saisail/mascarade/venv_tuning/bin/activate

LABEL="tuning-party-hf"
SEQ_LEN=1024
LOGDIR="runs/pipeline_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOGDIR"

# Domains configuration
SMALL_DOMAINS=(stm32 freecad iot dsp kicad emc platformio)
LARGE_DOMAINS=(embedded power)
SPICE_MAX_SAMPLES=20000

# Domains with deterministic validators (Phase B priority)
VALIDATOR_DOMAINS=(stm32 embedded spice kicad platformio)
# Domains with LLM judge only
LLM_JUDGE_DOMAINS=(dsp power emc iot freecad)
ALL_DOMAINS=("${SMALL_DOMAINS[@]}" "${LARGE_DOMAINS[@]}" spice)

# Parse arguments
SKIP_PHASE_A=false
ONLY_PHASE_B=false
ONLY_PHASE_C=false
for arg in "$@"; do
  case $arg in
    --skip-phase-a) SKIP_PHASE_A=true ;;
    --only-phase-b) ONLY_PHASE_B=true; SKIP_PHASE_A=true ;;
    --only-phase-c) ONLY_PHASE_C=true; SKIP_PHASE_A=true ;;
  esac
done

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGDIR/pipeline.log"
}

check_gpu() {
  if ! nvidia-smi > /dev/null 2>&1; then
    log "ERROR: GPU not available"
    exit 1
  fi
  log "GPU: $(nvidia-smi --query-gpu=name,memory.free --format=csv,noheader,nounits | head -1) MiB free"
}

# ============================================================
# PHASE A — SFT Training
# ============================================================
phase_a() {
  log "=========================================="
  log "PHASE A — SFT Training (Smart Strategy)"
  log "=========================================="

  # Small domains — 3 epochs
  for domain in "${SMALL_DOMAINS[@]}"; do
    log ">>> Phase A: Training $domain (3 epochs)"
    python run_local.py "$domain" \
      --device gpu --run-label "$LABEL" \
      --seq-len "$SEQ_LEN" --epochs 3 --eval --verbose \
      2>&1 | tee "$LOGDIR/phase_a_${domain}.log"
    log ">>> Done: $domain"
  done

  # Large domains — 1 epoch
  for domain in "${LARGE_DOMAINS[@]}"; do
    log ">>> Phase A: Training $domain (1 epoch)"
    python run_local.py "$domain" \
      --device gpu --run-label "$LABEL" \
      --seq-len "$SEQ_LEN" --epochs 1 --eval --verbose \
      2>&1 | tee "$LOGDIR/phase_a_${domain}.log"
    log ">>> Done: $domain"
  done

  # Spice — 1 epoch, capped
  log ">>> Phase A: Training spice (1 epoch, max ${SPICE_MAX_SAMPLES})"
  python run_local.py spice \
    --device gpu --run-label "$LABEL" \
    --seq-len "$SEQ_LEN" --epochs 1 --max-samples "$SPICE_MAX_SAMPLES" --eval --verbose \
    2>&1 | tee "$LOGDIR/phase_a_spice.log"
  log ">>> Done: spice"

  log "PHASE A COMPLETE"
}

# ============================================================
# MERGE & DEPLOY — Prepare models for Phase B
# ============================================================
phase_merge_deploy() {
  log "=========================================="
  log "MERGE & DEPLOY — Preparing models for rejection sampling"
  log "=========================================="

  for domain in "${ALL_DOMAINS[@]}"; do
    log ">>> Merge+GGUF+Deploy: $domain"
    # Find latest adapter for this domain
    ADAPTER_DIR=$(ls -dt runs/${LABEL}_${domain}_*/train_output 2>/dev/null | head -1)
    if [ -z "$ADAPTER_DIR" ]; then
      log "WARNING: No adapter found for $domain, skipping"
      continue
    fi
    python pipeline.py "$domain" --step merge --step gguf --step deploy \
      2>&1 | tee "$LOGDIR/merge_deploy_${domain}.log" || \
      log "WARNING: merge/deploy failed for $domain, continuing"
    log ">>> Done: $domain"
  done

  log "MERGE & DEPLOY COMPLETE"
}

# ============================================================
# PHASE B — Rejection Sampling + Validation
# ============================================================
phase_b() {
  log "=========================================="
  log "PHASE B — Rejection Sampling"
  log "=========================================="

  # Priority: domains with deterministic validators first
  for domain in "${VALIDATOR_DOMAINS[@]}"; do
    log ">>> Phase B: Rejection sampling $domain (deterministic validator)"
    python rejection_sampling.py "$domain" \
      --student-model "mascarade-$domain" \
      --n-candidates 8 \
      --max-prompts 500 \
      2>&1 | tee "$LOGDIR/phase_b_${domain}.log" || \
      log "WARNING: rejection sampling failed for $domain, continuing"
    log ">>> Done: $domain"
  done

  # Then LLM judge domains
  for domain in "${LLM_JUDGE_DOMAINS[@]}"; do
    log ">>> Phase B: Rejection sampling $domain (LLM judge)"
    python rejection_sampling.py "$domain" \
      --student-model "mascarade-$domain" \
      --n-candidates 8 \
      --max-prompts 500 \
      2>&1 | tee "$LOGDIR/phase_b_${domain}.log" || \
      log "WARNING: rejection sampling failed for $domain, continuing"
    log ">>> Done: $domain"
  done

  log "PHASE B COMPLETE"
}

# ============================================================
# PHASE C — DPO/ORPO Training
# ============================================================
phase_c() {
  log "=========================================="
  log "PHASE C — DPO Training"
  log "=========================================="

  for domain in "${ALL_DOMAINS[@]}"; do
    # Find DPO dataset
    DPO_DATASET=$(ls -t dpo_pairs/$domain/dpo_${domain}*.jsonl 2>/dev/null | head -1)
    if [ -z "$DPO_DATASET" ]; then
      log "WARNING: No DPO dataset for $domain, skipping Phase C"
      continue
    fi

    # Find adapter from Phase A
    ADAPTER_DIR=$(ls -dt runs/${LABEL}_${domain}_*/train_output 2>/dev/null | head -1)
    if [ -z "$ADAPTER_DIR" ]; then
      log "WARNING: No Phase A adapter for $domain, skipping"
      continue
    fi

    log ">>> Phase C: DPO training $domain"
    python train_dpo.py "$domain" \
      --model "$ADAPTER_DIR" \
      --dpo-dataset "$DPO_DATASET" \
      --method dpo --beta 0.1 --epochs 1 \
      2>&1 | tee "$LOGDIR/phase_c_${domain}.log" || \
      log "WARNING: DPO training failed for $domain, continuing"
    log ">>> Done: $domain"
  done

  log "PHASE C COMPLETE"
}

# ============================================================
# STATUS REPORT
# ============================================================
status_report() {
  log "=========================================="
  log "PIPELINE STATUS REPORT"
  log "=========================================="

  for domain in "${ALL_DOMAINS[@]}"; do
    phase_a_ok="?"
    phase_b_ok="?"
    phase_c_ok="?"

    # Check Phase A
    if ls runs/${LABEL}_${domain}_*/train_output/training_info.json > /dev/null 2>&1; then
      phase_a_ok="OK"
    else
      phase_a_ok="--"
    fi

    # Check Phase B
    if ls dpo_pairs/$domain/dpo_${domain}*.jsonl > /dev/null 2>&1; then
      phase_b_ok="OK"
    else
      phase_b_ok="--"
    fi

    # Check Phase C
    if ls runs/dpo_${domain}_*/training_info.json > /dev/null 2>&1; then
      phase_c_ok="OK"
    else
      phase_c_ok="--"
    fi

    log "  $domain: Phase A=$phase_a_ok  Phase B=$phase_b_ok  Phase C=$phase_c_ok"
  done
}

# ============================================================
# MAIN
# ============================================================
check_gpu

if $ONLY_PHASE_B; then
  phase_b
  status_report
  exit 0
fi

if $ONLY_PHASE_C; then
  phase_c
  status_report
  exit 0
fi

if ! $SKIP_PHASE_A; then
  phase_a
fi

phase_merge_deploy
phase_b
phase_c
status_report

log "=========================================="
log "FULL PIPELINE COMPLETE — $(date)"
log "=========================================="
