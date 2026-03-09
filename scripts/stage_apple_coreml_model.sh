#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEST_DIR="${APPLE_LLM_MODEL_DEST:-${HOME}/Models/mascarade/apple-llm/apple-coreml}"
MODEL_SOURCE=""
EMBED_SOURCE=""
TOKENIZER_SOURCE=""
MODEL_ID="${APPLE_LLM_MODEL_ID:-apple-coreml-local}"

usage() {
  cat <<'EOF'
Usage: scripts/stage_apple_coreml_model.sh [options]

Options:
  --model-source <path>      Path to the exported Core ML decoder artifact (.mlpackage or .mlmodelc)
  --tokenizer-source <dir>   Directory containing tokenizer assets
  --embed-source <path>      Optional path to a Core ML embed_tokens artifact
  --dest <dir>               Destination directory
  --model-id <id>            Model identifier to print in the export hints

Example:
  scripts/stage_apple_coreml_model.sh \
    --model-source ~/Exports/Qwen3.5/decoder_model_merged.mlpackage \
    --embed-source ~/Exports/Qwen3.5/embed_tokens.mlpackage \
    --tokenizer-source ~/Exports/Qwen3.5/tokenizer \
    --dest ~/Models/mascarade/apple-llm/Qwen3.5-4B-CoreML
EOF
}

copy_path() {
  local src="$1"
  local dest="$2"

  if [[ -e "$dest" ]]; then
    echo "Destination already exists: $dest" >&2
    exit 2
  fi

  if command -v ditto >/dev/null 2>&1; then
    ditto "$src" "$dest"
    return
  fi

  cp -R "$src" "$dest"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-source)
      MODEL_SOURCE="$2"
      shift 2
      ;;
    --embed-source)
      EMBED_SOURCE="$2"
      shift 2
      ;;
    --tokenizer-source)
      TOKENIZER_SOURCE="$2"
      shift 2
      ;;
    --dest)
      DEST_DIR="$2"
      shift 2
      ;;
    --model-id)
      MODEL_ID="$2"
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

if [[ -z "$MODEL_SOURCE" ]] || [[ -z "$TOKENIZER_SOURCE" ]]; then
  usage >&2
  exit 2
fi

if [[ ! -d "$TOKENIZER_SOURCE" ]]; then
  echo "Tokenizer source must be a directory: $TOKENIZER_SOURCE" >&2
  exit 2
fi

case "$MODEL_SOURCE" in
  *.mlpackage|*.mlmodelc)
    ;;
  *)
    echo "Model source must be a Core ML artifact (.mlpackage or .mlmodelc): $MODEL_SOURCE" >&2
    exit 2
    ;;
esac

if [[ -n "$EMBED_SOURCE" ]]; then
  case "$EMBED_SOURCE" in
    *.mlpackage|*.mlmodelc)
      ;;
    *)
      echo "Embed source must be a Core ML artifact (.mlpackage or .mlmodelc): $EMBED_SOURCE" >&2
      exit 2
      ;;
  esac
fi

mkdir -p "$DEST_DIR"

MODEL_NAME="$(basename "$MODEL_SOURCE")"
MODEL_DEST="${DEST_DIR}/${MODEL_NAME}"
TOKENIZER_DEST="${DEST_DIR}/tokenizer"
EMBED_DEST=""

copy_path "$MODEL_SOURCE" "$MODEL_DEST"
copy_path "$TOKENIZER_SOURCE" "$TOKENIZER_DEST"

if [[ -n "$EMBED_SOURCE" ]]; then
  EMBED_DEST="${DEST_DIR}/$(basename "$EMBED_SOURCE")"
  copy_path "$EMBED_SOURCE" "$EMBED_DEST"
fi

cat <<EOF
repo=${REPO_DIR}
dest=${DEST_DIR}
model_path=${MODEL_DEST}
tokenizer_path=${TOKENIZER_DEST}
EOF

if [[ -n "$EMBED_DEST" ]]; then
  printf 'embed_model_path=%s\n' "$EMBED_DEST"
fi

cat <<EOF

export APPLE_LLM_ENABLED=true
export APPLE_LLM_MODEL_ID=${MODEL_ID}
export APPLE_LLM_BACKEND=coreml
export APPLE_LLM_MODEL_PATH=${MODEL_DEST}
EOF

if [[ -n "$EMBED_DEST" ]]; then
  printf 'export APPLE_LLM_EMBED_MODEL_PATH=%s\n' "$EMBED_DEST"
fi

cat <<EOF
export APPLE_LLM_TOKENIZER_PATH=${TOKENIZER_DEST}
EOF
