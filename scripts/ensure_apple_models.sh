#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_ROOT="${APPLE_MODELS_ROOT:-${HOME}/Models/mascarade/apple-llm}"
CHECK_ONLY=false

usage() {
  cat <<'EOF'
Usage: scripts/ensure_apple_models.sh [options]

Options:
  --check-only    Verify the three Apple models without downloading anything
  -h, --help      Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      CHECK_ONLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

status=0

require_path() {
  local label="$1"
  local path="$2"
  if [[ -e "${path}" ]]; then
    echo "${label}: present (${path})"
    return 0
  fi
  echo "${label}: missing (${path})" >&2
  status=1
  return 1
}

ensure_qwen25_05b() {
  local dest="${MODELS_ROOT}/Qwen2.5-0.5B-Instruct-model"
  local model_path="${dest}/onnx/model.onnx"
  local tokenizer_path="${dest}"
  if [[ -e "${model_path}" && -d "${tokenizer_path}" ]]; then
    echo "qwen2.5-0.5b-instruct-onnx: present"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    require_path "qwen2.5-0.5b-instruct-onnx" "${model_path}" || true
    return 0
  fi
  "${SCRIPT_DIR}/install_apple_llm_model.sh" \
    --repo "onnx-community/Qwen2.5-0.5B-Instruct" \
    --onnx-file "model.onnx" \
    --dest "${dest}"
  require_path "qwen2.5-0.5b-instruct-onnx" "${model_path}" || true
}

ensure_qwen35_4b() {
  local dest="${MODELS_ROOT}/Qwen3.5-4B-ONNX-q4f16"
  local model_path="${dest}/onnx/decoder_model_merged_q4f16.onnx"
  local embed_path="${dest}/onnx/embed_tokens_q4f16.onnx"
  if [[ -e "${model_path}" && -e "${embed_path}" ]]; then
    echo "qwen3.5-4b-onnx-q4f16: present"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    require_path "qwen3.5-4b-onnx-q4f16" "${model_path}" || true
    require_path "qwen3.5-4b-onnx-q4f16 embed_tokens" "${embed_path}" || true
    return 0
  fi
  "${SCRIPT_DIR}/install_apple_llm_model.sh" \
    --repo "onnx-community/Qwen3.5-4B-ONNX" \
    --onnx-file "decoder_model_merged_q4f16.onnx" \
    --dest "${dest}"
  require_path "qwen3.5-4b-onnx-q4f16" "${model_path}" || true
  require_path "qwen3.5-4b-onnx-q4f16 embed_tokens" "${embed_path}" || true
}

ensure_stateful_mistral() {
  local dest="${MODELS_ROOT}/StatefulMistral7BInstructInt4"
  local model_path="${dest}/StatefulMistral7BInstructInt4.mlpackage"
  local tokenizer_path="${dest}/tokenizer"
  if [[ -e "${model_path}" && -d "${tokenizer_path}" ]]; then
    echo "stateful-mistral7b-instruct-int4-coreml: present"
    return 0
  fi
  if [[ "${CHECK_ONLY}" == "true" ]]; then
    require_path "stateful-mistral7b-instruct-int4-coreml" "${model_path}" || true
    require_path "stateful-mistral7b-instruct-int4-coreml tokenizer" "${tokenizer_path}" || true
    return 0
  fi
  "${SCRIPT_DIR}/install_apple_coreml_model.sh" \
    --repo "apple/mistral-coreml" \
    --artifact "StatefulMistral7BInstructInt4.mlpackage" \
    --tokenizer-repo "mistralai/Mistral-7B-Instruct-v0.3" \
    --dest "${dest}" \
    --model-id "stateful-mistral7b-instruct-int4-coreml"
  require_path "stateful-mistral7b-instruct-int4-coreml" "${model_path}" || true
  require_path "stateful-mistral7b-instruct-int4-coreml tokenizer" "${tokenizer_path}" || true
}

cd "${REPO_DIR}"
ensure_qwen25_05b
ensure_qwen35_4b
ensure_stateful_mistral

exit "${status}"
