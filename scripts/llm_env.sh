#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Source this file instead of executing it: . scripts/llm_env.sh" >&2
  exit 2
fi

: "${MASCARADE_LLM_DIR:=/ai/llm}"
export MASCARADE_LLM_DIR

HF_HOME="${MASCARADE_LLM_DIR}/huggingface"
export HF_HOME

HUGGINGFACE_HUB_CACHE="${HF_HOME}/hub"
export HUGGINGFACE_HUB_CACHE

TRANSFORMERS_CACHE="${HUGGINGFACE_HUB_CACHE}"
export TRANSFORMERS_CACHE

MASCARADE_MODELS_CACHE_DIR="${MASCARADE_LLM_DIR}/models_cache"
export MASCARADE_MODELS_CACHE_DIR

MASCARADE_WATCH_MODELS_DIR="${MASCARADE_LLM_DIR}/watch_models"
export MASCARADE_WATCH_MODELS_DIR

APPLE_LLM_MODEL_ROOT="${MASCARADE_LLM_DIR}/apple-llm"
export APPLE_LLM_MODEL_ROOT

mkdir -p \
  "${MASCARADE_LLM_DIR}" \
  "${HF_HOME}" \
  "${HUGGINGFACE_HUB_CACHE}" \
  "${MASCARADE_MODELS_CACHE_DIR}" \
  "${MASCARADE_WATCH_MODELS_DIR}" \
  "${APPLE_LLM_MODEL_ROOT}"
