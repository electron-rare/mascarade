#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/venv_tuning}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TORCH_CHANNEL="${TORCH_CHANNEL:-cu124}"
TORCH_VERSION="${TORCH_VERSION:-2.5.1}"
TRANSFORMERS_CHANNEL="${TRANSFORMERS_CHANNEL:-stable}"
TRANSFORMERS_STABLE_VERSION="${TRANSFORMERS_STABLE_VERSION:-4.57.6}"
HF_HUB_STABLE_SPEC="${HF_HUB_STABLE_SPEC:-huggingface_hub[cli]==0.35.3}"
REQ_FILE="$ROOT_DIR/finetune/requirements.txt"

case "$TORCH_CHANNEL" in
    cpu)
        TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"
        TORCH_SPEC="torch==${TORCH_VERSION}"
        ;;
    cu118|cu121|cu124)
        TORCH_INDEX_URL="https://download.pytorch.org/whl/${TORCH_CHANNEL}"
        TORCH_SPEC="torch==${TORCH_VERSION}+${TORCH_CHANNEL}"
        ;;
    *)
        echo "Unsupported TORCH_CHANNEL: ${TORCH_CHANNEL}" >&2
        echo "Expected one of: cpu, cu118, cu121, cu124" >&2
        exit 1
        ;;
esac

if [ ! -f "$REQ_FILE" ]; then
    echo "Requirements file not found: $REQ_FILE" >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install --index-url "$TORCH_INDEX_URL" "$TORCH_SPEC"
python -m pip install -r "$REQ_FILE"

case "$TRANSFORMERS_CHANNEL" in
    stable)
        python -m pip install --upgrade \
            "transformers==${TRANSFORMERS_STABLE_VERSION}" \
            "$HF_HUB_STABLE_SPEC"
        ;;
    main)
        python -m pip install --upgrade \
            "huggingface_hub[cli]>=1.3,<2" \
            "git+https://github.com/huggingface/transformers.git"
        ;;
    *)
        echo "Unsupported TRANSFORMERS_CHANNEL: ${TRANSFORMERS_CHANNEL}" >&2
        echo "Expected one of: stable, main" >&2
        exit 1
        ;;
esac

echo "[bootstrap-finetune-env]"
echo "torch_channel=${TORCH_CHANNEL}"
echo "transformers_channel=${TRANSFORMERS_CHANNEL}"

python "$ROOT_DIR/test_environment.py"
