#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Highest parallel load validated cleanly on this RTX 4090 so far.
MODE="${MODE:-triple-mixed-768}"
STOP_COMFYUI="${STOP_COMFYUI:-1}"
TOKENIZE_WORKERS="${TOKENIZE_WORKERS:-2}"
EPOCHS="${EPOCHS:-1}"
Q8B_MODEL="${Q8B_MODEL:-Qwen/Qwen3-8B}"
Q4B_MODEL="${Q4B_MODEL:-Qwen/Qwen3-4B-Instruct-2507}"

export MODE STOP_COMFYUI TOKENIZE_WORKERS EPOCHS Q8B_MODEL Q4B_MODEL

exec "$ROOT_DIR/scripts/triple_train_4090.sh"
