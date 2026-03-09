#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOOLS_VENV="${APPLE_LLM_HF_VENV_DIR:-${REPO_DIR}/.venv-hf-tools}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MODEL_REPO="${APPLE_COREML_MODEL_REPO:-apple/mistral-coreml}"
MODEL_REVISION="${APPLE_COREML_MODEL_REVISION:-main}"
MODEL_ARTIFACT="${APPLE_COREML_MODEL_ARTIFACT:-StatefulMistral7BInstructInt4.mlpackage}"
TOKENIZER_REPO="${APPLE_COREML_TOKENIZER_REPO:-mistralai/Mistral-7B-Instruct-v0.3}"
TOKENIZER_REVISION="${APPLE_COREML_TOKENIZER_REVISION:-main}"
DEST_DIR="${APPLE_COREML_MODEL_DEST:-${HOME}/Models/mascarade/apple-llm/StatefulMistral7BInstructInt4}"
MODEL_ID="${APPLE_LLM_MODEL_ID:-stateful-mistral7b-instruct-int4-coreml}"

usage() {
  cat <<'EOF'
Usage: scripts/install_apple_coreml_model.sh [options]

Options:
  --repo <repo>               Hugging Face repo id containing the Core ML artifact
  --revision <rev>            Repo revision or branch
  --artifact <name>           Core ML artifact directory name (.mlpackage or .mlmodelc)
  --tokenizer-repo <repo>     Hugging Face repo id for tokenizer assets
  --tokenizer-revision <rev>  Tokenizer repo revision or branch
  --dest <dir>                Destination directory
  --model-id <id>             Model identifier to print in env hints

Defaults:
  repo:               apple/mistral-coreml
  revision:           main
  artifact:           StatefulMistral7BInstructInt4.mlpackage
  tokenizer-repo:     mistralai/Mistral-7B-Instruct-v0.3
  tokenizer-revision: main
  dest:               ~/Models/mascarade/apple-llm/StatefulMistral7BInstructInt4
  model-id:           stateful-mistral7b-instruct-int4-coreml
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
    --artifact)
      MODEL_ARTIFACT="$2"
      shift 2
      ;;
    --tokenizer-repo)
      TOKENIZER_REPO="$2"
      shift 2
      ;;
    --tokenizer-revision)
      TOKENIZER_REVISION="$2"
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

case "$MODEL_ARTIFACT" in
  *.mlpackage|*.mlmodelc)
    ;;
  *)
    echo "Artifact must be a Core ML artifact directory (.mlpackage or .mlmodelc): $MODEL_ARTIFACT" >&2
    exit 2
    ;;
esac

mkdir -p "${DEST_DIR}"

if [[ ! -x "${TOOLS_VENV}/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${TOOLS_VENV}"
  "${TOOLS_VENV}/bin/pip" install --upgrade pip
  "${TOOLS_VENV}/bin/pip" install "huggingface_hub[hf_xet]>=0.34,<1"
fi

export APPLE_COREML_MODEL_REPO="${MODEL_REPO}"
export APPLE_COREML_MODEL_REVISION="${MODEL_REVISION}"
export APPLE_COREML_MODEL_ARTIFACT="${MODEL_ARTIFACT}"
export APPLE_COREML_TOKENIZER_REPO="${TOKENIZER_REPO}"
export APPLE_COREML_TOKENIZER_REVISION="${TOKENIZER_REVISION}"
export APPLE_COREML_MODEL_DEST="${DEST_DIR}"
export APPLE_COREML_MODEL_ID="${MODEL_ID}"

"${TOOLS_VENV}/bin/python" <<'PY'
import os
from pathlib import Path

from huggingface_hub import snapshot_download

model_repo = os.environ["APPLE_COREML_MODEL_REPO"]
model_revision = os.environ["APPLE_COREML_MODEL_REVISION"]
model_artifact = os.environ["APPLE_COREML_MODEL_ARTIFACT"]
tokenizer_repo = os.environ["APPLE_COREML_TOKENIZER_REPO"]
tokenizer_revision = os.environ["APPLE_COREML_TOKENIZER_REVISION"]
dest_dir = Path(os.environ["APPLE_COREML_MODEL_DEST"]).expanduser()
model_id = os.environ["APPLE_COREML_MODEL_ID"]

dest_dir.mkdir(parents=True, exist_ok=True)
tokenizer_dir = dest_dir / "tokenizer"

snapshot_download(
    repo_id=model_repo,
    revision=model_revision,
    local_dir=str(dest_dir),
    allow_patterns=[
        f"{model_artifact}/*",
        "README*",
        "LICENSE*",
    ],
)

snapshot_download(
    repo_id=tokenizer_repo,
    revision=tokenizer_revision,
    local_dir=str(tokenizer_dir),
    allow_patterns=[
        "tokenizer*",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "generation_config.json",
        "config.json",
        "added_tokens.json",
        "chat_template*",
    ],
)

model_path = dest_dir / model_artifact
if not model_path.exists():
    raise SystemExit(f"Core ML artifact was not downloaded: {model_path}")

print(f"repo={model_repo}")
print(f"tokenizer_repo={tokenizer_repo}")
print(f"dest={dest_dir}")
print(f"model_path={model_path}")
print(f"tokenizer_path={tokenizer_dir}")
print()
print("export APPLE_LLM_ENABLED=true")
print("export APPLE_LLM_BASE_URL=http://host.docker.internal:8201")
print(f"export APPLE_LLM_MODEL_ID={model_id}")
print("export APPLE_LLM_BACKEND=coreml")
print(f"export APPLE_LLM_MODEL_PATH={model_path}")
print(f"export APPLE_LLM_TOKENIZER_PATH={tokenizer_dir}")
PY
