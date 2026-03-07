#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Aggressive but still realistic preset for RTX 4090 24 GB on the current
# QLoRA trainer. Keep everything overridable through env vars.
export TEACHER_PROVIDER="${TEACHER_PROVIDER:-ollama}"
export TEACHER_MODEL="${TEACHER_MODEL:-qwen2.5:14b}"
export STUDENT_MODEL="${STUDENT_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"

export MAX_SOURCE_SAMPLES="${MAX_SOURCE_SAMPLES:-128}"
export SAMPLES_PER_SOURCE="${SAMPLES_PER_SOURCE:-2}"
export STUDENT_MAX_SAMPLES="${STUDENT_MAX_SAMPLES:-384}"
export SEQ_LEN="${SEQ_LEN:-1536}"
export EPOCHS="${EPOCHS:-2}"
export TOKENIZE_WORKERS="${TOKENIZE_WORKERS:-20}"
export DISTILL_CONCURRENCY="${DISTILL_CONCURRENCY:-1}"
export TIMEOUT="${TIMEOUT:-120}"
export UNLOAD_OLLAMA_BEFORE_RUN="${UNLOAD_OLLAMA_BEFORE_RUN:-1}"
export UNLOAD_COMFYUI_BEFORE_RUN="${UNLOAD_COMFYUI_BEFORE_RUN:-1}"
export COMFYUI_API_URL="${COMFYUI_API_URL:-http://127.0.0.1:8188}"

echo "[preset-stm32-4090]"
echo "teacher=${TEACHER_PROVIDER}/${TEACHER_MODEL}"
echo "student=${STUDENT_MODEL}"
echo "max_source_samples=${MAX_SOURCE_SAMPLES}"
echo "samples_per_source=${SAMPLES_PER_SOURCE}"
echo "student_max_samples=${STUDENT_MAX_SAMPLES}"
echo "seq_len=${SEQ_LEN}"
echo "epochs=${EPOCHS}"
echo "tokenize_workers=${TOKENIZE_WORKERS}"
echo "distill_concurrency=${DISTILL_CONCURRENCY}"
echo "timeout=${TIMEOUT}"

exec "$ROOT_DIR/scripts/finetune_host_gpu.sh" stm32 "$@"
