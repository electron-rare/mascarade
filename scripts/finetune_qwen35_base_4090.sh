#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

DOMAIN="${DOMAIN:-stm32}"
if [[ $# -gt 0 && "${1#-}" == "$1" ]]; then
    DOMAIN="$1"
    shift
fi

# Solo-oriented preset for Qwen3.5-9B-Base on RTX 4090.
# This path requires a transformers build with qwen3_5 support.
export TRANSFORMERS_CHANNEL="${TRANSFORMERS_CHANNEL:-main}"
export TEACHER_PROVIDER="${TEACHER_PROVIDER:-ollama}"
export TEACHER_MODEL="${TEACHER_MODEL:-qwen2.5:14b}"
export STUDENT_MODEL="${STUDENT_MODEL:-Qwen/Qwen3.5-9B-Base}"

export MAX_SOURCE_SAMPLES="${MAX_SOURCE_SAMPLES:-64}"
export SAMPLES_PER_SOURCE="${SAMPLES_PER_SOURCE:-2}"
export STUDENT_MAX_SAMPLES="${STUDENT_MAX_SAMPLES:-128}"
export SEQ_LEN="${SEQ_LEN:-1024}"
export EPOCHS="${EPOCHS:-1}"
export TOKENIZE_WORKERS="${TOKENIZE_WORKERS:-12}"
export DISTILL_CONCURRENCY="${DISTILL_CONCURRENCY:-1}"
export TIMEOUT="${TIMEOUT:-120}"
export UNLOAD_OLLAMA_BEFORE_RUN="${UNLOAD_OLLAMA_BEFORE_RUN:-1}"
export UNLOAD_COMFYUI_BEFORE_RUN="${UNLOAD_COMFYUI_BEFORE_RUN:-1}"
export COMFYUI_API_URL="${COMFYUI_API_URL:-http://127.0.0.1:8188}"

echo "[preset-qwen35-base-4090]"
echo "domain=${DOMAIN}"
echo "transformers_channel=${TRANSFORMERS_CHANNEL}"
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

exec "$ROOT_DIR/scripts/finetune_host_gpu.sh" "$DOMAIN" "$@"
