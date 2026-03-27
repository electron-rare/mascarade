#!/bin/bash
# Phase D — Adapter deployment: merge → GGUF → Ollama → HuggingFace upload
# Runs after Phase C DPO/ORPO training.
#
# Steps:
#   1. deploy_all.sh: merge LoRA into base, quantize to GGUF, register in Ollama
#   2. huggingface-cli: upload adapters to clemsail/mascarade-{domain}-lora
#
# Prerequisites:
#   huggingface-cli login
#   llama-quantize in PATH (or ./llama-quantize)
#
# Usage (on KXKM-AI):
#   ./batch_phase_d.sh
#   ./batch_phase_d.sh --domains stm32,kicad
#   ./batch_phase_d.sh --skip-hf     # local deploy only
#   ./batch_phase_d.sh --skip-deploy # HF upload only

set -euo pipefail
cd "$(dirname "$0")"

VENV="/ai/saisail/mascarade/venv_tuning/bin/activate"
if [ -f "${VENV}" ]; then
  # shellcheck source=/dev/null
  source "${VENV}"
fi

HF_USER="${HF_USER:-clemsail}"
DOMAINS_ALL="stm32 embedded spice kicad platformio iot dsp emc power freecad"
SKIP_HF=false
SKIP_DEPLOY=false

# Parse args
SELECTED_DOMAINS=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --domains) SELECTED_DOMAINS="${2//,/ }"; shift 2 ;;
    --skip-hf) SKIP_HF=true; shift ;;
    --skip-deploy) SKIP_DEPLOY=true; shift ;;
    --hf-user) HF_USER="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done
DOMAINS="${SELECTED_DOMAINS:-${DOMAINS_ALL}}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="runs/phase_d_${TIMESTAMP}"
mkdir -p "${LOG_DIR}"

echo "=========================================="
echo "Phase D — Deploy + HuggingFace Upload"
echo "HF user:  ${HF_USER}"
echo "Start:    $(date)"
echo "Domains:  ${DOMAINS}"
echo "Skip HF:  ${SKIP_HF}"
echo "=========================================="

# Step 1: merge + GGUF + Ollama via deploy_all.sh
if [ "${SKIP_DEPLOY}" = false ]; then
  echo ""
  echo "--- Step 1: merge → GGUF → Ollama ---"
  domain_csv="${DOMAINS// /,}"
  if ./deploy_all.sh --domains "${domain_csv}" 2>&1 | tee "${LOG_DIR}/deploy_all.log"; then
    echo "[D] deploy_all.sh OK"
  else
    echo "[WARN] deploy_all.sh exited non-zero — continuing with HF upload"
  fi
fi

# Step 2: HF upload
if [ "${SKIP_HF}" = false ]; then
  echo ""
  echo "--- Step 2: HuggingFace upload ---"

  if ! huggingface-cli whoami &>/dev/null; then
    echo "[ERROR] Not logged in to HuggingFace. Run: huggingface-cli login"
    exit 1
  fi

  FAILED_HF=()

  for domain in ${DOMAINS}; do
    echo ""
    echo ">>> [D/HF] ${domain} — $(date)"

    # Prefer DPO adapter (Phase C), fall back to SFT adapter (Phase A)
    adapter_dir=$(
      ls -td "runs/"*"${domain}"*"_dpo/train_output/adapter" 2>/dev/null | head -1 || \
      ls -td "runs/tuning-party-hf_${domain}"*/train_output/adapter 2>/dev/null | head -1 || \
      true
    )

    if [ -z "${adapter_dir}" ]; then
      echo "  [SKIP] No adapter for ${domain}"
      continue
    fi

    repo="${HF_USER}/mascarade-${domain}-lora"
    echo "  Adapter: ${adapter_dir}"
    echo "  Repo:    ${repo}"

    if python - <<PYEOF 2>&1 | tee "${LOG_DIR}/hf_${domain}.log"; then
from huggingface_hub import HfApi
import json, pathlib

api = HfApi()
api.create_repo("${repo}", repo_type="model", exist_ok=True)

# Add model card if not present
adapter_path = pathlib.Path("${adapter_dir}")
card_path = adapter_path / "README.md"
if not card_path.exists():
    card_path.write_text(
        "---\n"
        "library_name: peft\n"
        "base_model: Qwen/Qwen2.5-Coder-3B-Instruct\n"
        "tags:\n"
        "  - mascarade\n"
        "  - electronics\n"
        "  - embedded\n"
        f"  - ${domain}\n"
        "---\n\n"
        f"# mascarade-${domain}-lora\n\n"
        "LoRA adapter fine-tuned on the mascarade ${domain} domain dataset.\n"
        "Phase C ORPO training on top of Phase A SFT.\n"
    )

api.upload_folder(
    folder_path="${adapter_dir}",
    repo_id="${repo}",
    repo_type="model",
    commit_message="Phase D upload ${TIMESTAMP}",
)
print(f"Uploaded to https://huggingface.co/${repo}")
PYEOF
      echo ">>> [D/HF] ${domain} OK"
    else
      echo ">>> [D/HF] ${domain} FAILED"
      FAILED_HF+=("${domain}")
    fi
  done

  if [ ${#FAILED_HF[@]} -gt 0 ]; then
    echo "HF upload FAILED: ${FAILED_HF[*]}"
  fi
fi

echo ""
echo "=========================================="
echo "Phase D COMPLETE — $(date)"
echo "Check: https://huggingface.co/${HF_USER}"
echo "Review then: set mascarade-components-review status"
echo "=========================================="
