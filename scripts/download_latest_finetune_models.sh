#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

. "$ROOT_DIR/scripts/llm_env.sh"

if [ ! -d venv_tuning ]; then
  echo "venv_tuning missing; run ./scripts/bootstrap_finetune_env.sh first" >&2
  exit 1
fi

. venv_tuning/bin/activate

models=(
  "Qwen/Qwen3.5-9B-Base"
  "Qwen/Qwen3.5-35B-A3B-GPTQ-Int4"
  "mistralai/Devstral-Small-2-24B-Instruct-2512"
  "mistralai/Mistral-Small-3.1-24B-Base-2503"
)

python3 - <<'PY' "${models[@]}"
import sys
from pathlib import Path
import os

root = Path(os.environ["HUGGINGFACE_HUB_CACHE"])
for model in sys.argv[1:]:
    cache_dir = root / f"models--{model.replace('/', '--')}"
    if cache_dir.exists():
        print(f"[cached] {model}")
    else:
        print(f"[download] {model}")
PY

echo "[llm-root] $MASCARADE_LLM_DIR"

for model in "${models[@]}"; do
  python "$ROOT_DIR/finetune/probe_hf_repo.py" "$model" --repo-type model >/dev/null
  echo "[download] $model"
  python - <<'PY' "$model"
import sys
from huggingface_hub import snapshot_download

snapshot_download(sys.argv[1])
PY
done
