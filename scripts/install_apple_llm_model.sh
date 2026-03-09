#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
. "${REPO_DIR}/scripts/llm_env.sh"
TOOLS_VENV="${APPLE_LLM_HF_VENV_DIR:-${REPO_DIR}/.venv-hf-tools}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MODEL_REPO="${APPLE_LLM_MODEL_REPO:-onnx-community/Qwen3.5-4B-ONNX}"
MODEL_REVISION="${APPLE_LLM_MODEL_REVISION:-main}"
ONNX_FILE="${APPLE_LLM_ONNX_FILE:-decoder_model_merged_q4f16.onnx}"
DEST_DIR="${APPLE_LLM_MODEL_DEST:-${APPLE_LLM_MODEL_ROOT}/Qwen3.5-4B-ONNX-q4f16}"
EMBED_ONNX_FILE=""

usage() {
  cat <<'EOF'
Usage: scripts/install_apple_llm_model.sh [options]

Options:
  --repo <repo>         Hugging Face repo id
  --revision <rev>      Repo revision or branch
  --onnx-file <file>    File inside onnx/ to fetch
  --dest <dir>          Destination directory

Defaults:
  repo:      onnx-community/Qwen3.5-4B-ONNX
  revision:  main
  onnx-file: decoder_model_merged_q4f16.onnx
  dest:      /ai/llm/apple-llm/Qwen3.5-4B-ONNX-q4f16
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      MODEL_REPO="$2"
      shift 2
      ;;
    --revision)
      MODEL_REVISION="$2"
      shift 2
      ;;
    --onnx-file)
      ONNX_FILE="$2"
      shift 2
      ;;
    --dest)
      DEST_DIR="$2"
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

mkdir -p "${DEST_DIR}"

if [[ "${ONNX_FILE}" == decoder_model_merged* ]]; then
  EMBED_ONNX_FILE="embed_tokens${ONNX_FILE#decoder_model_merged}"
elif [[ "${ONNX_FILE}" == decoder_model* ]]; then
  EMBED_ONNX_FILE="embed_tokens${ONNX_FILE#decoder_model}"
fi

if [[ ! -x "${TOOLS_VENV}/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${TOOLS_VENV}"
  "${TOOLS_VENV}/bin/pip" install --upgrade pip
  "${TOOLS_VENV}/bin/pip" install "huggingface_hub[hf_xet]>=0.34,<1"
fi

export APPLE_LLM_MODEL_REPO="${MODEL_REPO}"
export APPLE_LLM_MODEL_REVISION="${MODEL_REVISION}"
export APPLE_LLM_ONNX_FILE="${ONNX_FILE}"
export APPLE_LLM_EMBED_ONNX_FILE="${EMBED_ONNX_FILE}"
export APPLE_LLM_MODEL_DEST="${DEST_DIR}"

"${TOOLS_VENV}/bin/python" <<'PY'
import os
from huggingface_hub import snapshot_download

repo_id = os.environ["APPLE_LLM_MODEL_REPO"]
revision = os.environ["APPLE_LLM_MODEL_REVISION"]
onnx_file = os.environ["APPLE_LLM_ONNX_FILE"]
embed_onnx_file = os.environ.get("APPLE_LLM_EMBED_ONNX_FILE", "").strip()
dest_dir = os.environ["APPLE_LLM_MODEL_DEST"]

patterns = [
    "config.json",
    "generation_config.json",
    "special_tokens_map.json",
    "tokenizer*",
    "processor_config.json",
    "preprocessor_config.json",
    "chat_template*",
    "added_tokens.json",
    f"onnx/{onnx_file}*",
]

if embed_onnx_file:
    patterns.append(f"onnx/{embed_onnx_file}*")

snapshot_download(
    repo_id=repo_id,
    revision=revision,
    local_dir=dest_dir,
    allow_patterns=patterns,
)

print(f"repo={repo_id}")
print(f"dest={dest_dir}")
print(f"llm_root={os.environ.get('MASCARADE_LLM_DIR', '')}")
print(f"model_path={os.path.join(dest_dir, 'onnx', onnx_file)}")
if embed_onnx_file:
    print(f"embed_model_path={os.path.join(dest_dir, 'onnx', embed_onnx_file)}")
print(f"tokenizer_path={dest_dir}")
PY
