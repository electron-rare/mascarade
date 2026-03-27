#!/bin/bash
# Phase C — DPO/ORPO Preference Training
# Runs after Phase B rejection sampling.
# Takes DPO pairs, trains student model to prefer correct outputs.
#
# Method: ORPO (no reference model — saves ~3GB VRAM, ideal for 3B models)
# Override: METHOD=dpo ./batch_phase_c.sh  (for Qwen3.5-9B+)
#
# Usage (on KXKM-AI):
#   ./batch_phase_c.sh
#   ./batch_phase_c.sh --domains stm32,kicad
#   METHOD=dpo ./batch_phase_c.sh

set -euo pipefail
cd "$(dirname "$0")"

VENV="/ai/saisail/mascarade/venv_tuning/bin/activate"
if [ -f "${VENV}" ]; then
  # shellcheck source=/dev/null
  source "${VENV}"
fi

METHOD="${METHOD:-orpo}"
LABEL="tuning-party-hf"
DOMAINS_ALL="stm32 embedded spice kicad platformio iot dsp emc power freecad"

# Parse args
SELECTED_DOMAINS=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --domains) SELECTED_DOMAINS="${2//,/ }"; shift 2 ;;
    --method) METHOD="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done
DOMAINS="${SELECTED_DOMAINS:-${DOMAINS_ALL}}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="runs/phase_c_${TIMESTAMP}"
mkdir -p "${LOG_DIR}"

echo "=========================================="
echo "Phase C — DPO/ORPO Training"
echo "Method:  ${METHOD}"
echo "Start:   $(date)"
echo "Domains: ${DOMAINS}"
echo "Log dir: ${LOG_DIR}"
echo "=========================================="

FAILED_DOMAINS=()
SKIPPED_DOMAINS=()

for domain in ${DOMAINS}; do
  echo ""
  echo ">>> [C] ${domain} — $(date)"

  # Find latest DPO pairs file
  dpo_file=$(ls -t "dpo_pairs/${domain}"/dpo_*.jsonl 2>/dev/null | head -1 || true)
  if [ -z "${dpo_file}" ]; then
    echo "  [SKIP] No DPO pairs for ${domain} — run batch_phase_b.sh first"
    SKIPPED_DOMAINS+=("${domain}")
    continue
  fi

  # Find latest Phase A SFT adapter (prefer most recent tuning-party-hf run)
  sft_adapter=$(ls -td "runs/${LABEL}_${domain}"*/train_output/adapter 2>/dev/null | head -1 || true)
  if [ -z "${sft_adapter}" ]; then
    sft_adapter="Qwen/Qwen2.5-Coder-3B-Instruct"
    echo "  [WARN] No Phase A adapter for ${domain}, using base model: ${sft_adapter}"
  else
    echo "  SFT adapter: ${sft_adapter}"
  fi

  echo "  DPO pairs:   ${dpo_file}"
  echo "  Method:      ${METHOD}"

  if python train_dpo.py "${domain}" \
    --model "${sft_adapter}" \
    --dpo-dataset "${dpo_file}" \
    --method "${METHOD}" \
    --epochs 1 \
    2>&1 | tee "${LOG_DIR}/${domain}.log"; then
    echo ">>> [C] ${domain} OK"
  else
    echo ">>> [C] ${domain} FAILED"
    FAILED_DOMAINS+=("${domain}")
  fi
done

echo ""
echo "=========================================="
echo "Phase C COMPLETE — $(date)"
echo "Adapters:"
for domain in ${DOMAINS}; do
  adapter=$(ls -td "runs/"*"${domain}"*"_dpo/train_output/adapter" 2>/dev/null | head -1 || true)
  if [ -n "${adapter}" ]; then
    echo "  ${domain}: ${adapter}"
  else
    echo "  ${domain}: (not found)"
  fi
done
if [ ${#SKIPPED_DOMAINS[@]} -gt 0 ]; then
  echo "SKIPPED (no DPO pairs): ${SKIPPED_DOMAINS[*]}"
fi
if [ ${#FAILED_DOMAINS[@]} -gt 0 ]; then
  echo "FAILED: ${FAILED_DOMAINS[*]}"
fi
echo "Next: ./batch_phase_d.sh"
echo "=========================================="
