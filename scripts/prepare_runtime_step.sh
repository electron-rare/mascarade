#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_ROOT="${APPLE_MODELS_ROOT:-${HOME}/Models/mascarade/apple-llm}"
APPLE_MODEL=""
RESTART_TARGET=""
RESUME_STATE=""
ANE_SCRIPT=""

usage() {
  cat <<'EOF'
Usage: scripts/prepare_runtime_step.sh [options]

Options:
  --apple-model <id>      Prepare the manual commands to switch the Apple runtime to a known model id
  --restart <target>      Prepare a restart command for `core` or `apple`
  --resume-state <path>   State file to resume in ai-novel-engine
  --ane-script <path>     Path to ai-novel-engine/scripts/run_next_lots.py
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apple-model)
      APPLE_MODEL="${2:-}"
      shift 2
      ;;
    --restart)
      RESTART_TARGET="${2:-}"
      shift 2
      ;;
    --resume-state)
      RESUME_STATE="${2:-}"
      shift 2
      ;;
    --ane-script)
      ANE_SCRIPT="${2:-}"
      shift 2
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

if [[ -n "${APPLE_MODEL}" && -n "${RESTART_TARGET}" ]]; then
  echo "Choose either --apple-model or --restart, not both." >&2
  exit 2
fi

if [[ -z "${APPLE_MODEL}" && -z "${RESTART_TARGET}" ]]; then
  usage >&2
  exit 2
fi

print_resume_hint() {
  if [[ -n "${RESUME_STATE}" && -n "${ANE_SCRIPT}" ]]; then
    printf '\n# resume\npython3 %q --resume %q\n' "${ANE_SCRIPT}" "${RESUME_STATE}"
  fi
}

apple_profile() {
  case "${APPLE_MODEL}" in
    qwen2.5-0.5b-instruct-onnx)
      cat <<EOF
export APPLE_LLM_ENABLED=true
export APPLE_LLM_BASE_URL=http://host.docker.internal:8201
export APPLE_LLM_MODEL_ID=qwen2.5-0.5b-instruct-onnx
export APPLE_LLM_BACKEND=onnx-coreml
export APPLE_LLM_MODEL_PATH=${MODELS_ROOT}/Qwen2.5-0.5B-Instruct-model/onnx/model.onnx
export APPLE_LLM_EMBED_MODEL_PATH=
export APPLE_LLM_TOKENIZER_PATH=${MODELS_ROOT}/Qwen2.5-0.5B-Instruct-model
export APPLE_LLM_ENABLE_THINKING=false
EOF
      ;;
    qwen3.5-4b-onnx-q4f16)
      cat <<EOF
export APPLE_LLM_ENABLED=true
export APPLE_LLM_BASE_URL=http://host.docker.internal:8201
export APPLE_LLM_MODEL_ID=qwen3.5-4b-onnx-q4f16
export APPLE_LLM_BACKEND=onnx-coreml
export APPLE_LLM_MODEL_PATH=${MODELS_ROOT}/Qwen3.5-4B-ONNX-q4f16/onnx/decoder_model_merged_q4f16.onnx
export APPLE_LLM_EMBED_MODEL_PATH=${MODELS_ROOT}/Qwen3.5-4B-ONNX-q4f16/onnx/embed_tokens_q4f16.onnx
export APPLE_LLM_TOKENIZER_PATH=${MODELS_ROOT}/Qwen3.5-4B-ONNX-q4f16
export APPLE_LLM_ENABLE_THINKING=false
EOF
      ;;
    stateful-mistral7b-instruct-int4-coreml)
      cat <<EOF
export APPLE_LLM_ENABLED=true
export APPLE_LLM_BASE_URL=http://host.docker.internal:8201
export APPLE_LLM_MODEL_ID=stateful-mistral7b-instruct-int4-coreml
export APPLE_LLM_BACKEND=coreml
export APPLE_LLM_MODEL_PATH=${MODELS_ROOT}/StatefulMistral7BInstructInt4/StatefulMistral7BInstructInt4.mlpackage
export APPLE_LLM_EMBED_MODEL_PATH=
export APPLE_LLM_TOKENIZER_PATH=${MODELS_ROOT}/StatefulMistral7BInstructInt4/tokenizer
export APPLE_LLM_ENABLE_THINKING=false
EOF
      ;;
    *)
      echo "Unknown Apple model id: ${APPLE_MODEL}" >&2
      exit 2
      ;;
  esac
}

verify_profile_paths() {
  local model_path
  local tokenizer_path
  local embed_path

  case "${APPLE_MODEL}" in
    qwen2.5-0.5b-instruct-onnx)
      model_path="${MODELS_ROOT}/Qwen2.5-0.5B-Instruct-model/onnx/model.onnx"
      tokenizer_path="${MODELS_ROOT}/Qwen2.5-0.5B-Instruct-model"
      embed_path=""
      ;;
    qwen3.5-4b-onnx-q4f16)
      model_path="${MODELS_ROOT}/Qwen3.5-4B-ONNX-q4f16/onnx/decoder_model_merged_q4f16.onnx"
      tokenizer_path="${MODELS_ROOT}/Qwen3.5-4B-ONNX-q4f16"
      embed_path="${MODELS_ROOT}/Qwen3.5-4B-ONNX-q4f16/onnx/embed_tokens_q4f16.onnx"
      ;;
    stateful-mistral7b-instruct-int4-coreml)
      model_path="${MODELS_ROOT}/StatefulMistral7BInstructInt4/StatefulMistral7BInstructInt4.mlpackage"
      tokenizer_path="${MODELS_ROOT}/StatefulMistral7BInstructInt4/tokenizer"
      embed_path=""
      ;;
    *)
      return
      ;;
  esac

  [[ -e "${model_path}" ]] || { echo "Missing model path: ${model_path}" >&2; exit 2; }
  [[ -d "${tokenizer_path}" ]] || { echo "Missing tokenizer path: ${tokenizer_path}" >&2; exit 2; }
  if [[ -n "${embed_path}" ]]; then
    [[ -e "${embed_path}" ]] || { echo "Missing embed path: ${embed_path}" >&2; exit 2; }
  fi
}

if [[ -n "${RESTART_TARGET}" ]]; then
  case "${RESTART_TARGET}" in
    core)
      cat <<EOF
# restart core/api
cd ${REPO_DIR}
docker compose restart core api
EOF
      ;;
    apple)
      cat <<EOF
# restart Apple runtime
cd ${REPO_DIR}
pkill -f "uvicorn app:app" || true
bash scripts/run_apple_llm_service.sh
EOF
      ;;
    *)
      echo "Unknown restart target: ${RESTART_TARGET}" >&2
      exit 2
      ;;
  esac
  print_resume_hint
  exit 0
fi

verify_profile_paths

cat <<EOF
# switch Apple runtime model
cd ${REPO_DIR}
$(apple_profile)
pkill -f "uvicorn app:app" || true
bash scripts/run_apple_llm_service.sh
curl -fsS http://127.0.0.1:8201/health
curl -fsS http://127.0.0.1:8201/models
EOF

print_resume_hint
