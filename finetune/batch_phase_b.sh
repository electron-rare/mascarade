#!/bin/bash
# Phase B — Rejection Sampling (DPO pair generation)
# Runs after Phase A SFT training completes on KXKM-AI.
# For each domain: generates N candidates, validates with deterministic tools,
# builds chosen/rejected DPO preference pairs.
#
# Prerequisites:
#   gcc-arm-none-eabi  (stm32/embedded validators)
#   ngspice            (spice validator)
#   KiCad CLI          (kicad validator)
#
# Usage (on KXKM-AI):
#   ./batch_phase_b.sh
#   ./batch_phase_b.sh --domains stm32,kicad   # subset
#   ./batch_phase_b.sh --n-candidates 4         # faster for test
#   N_CANDIDATES=4 ./batch_phase_b.sh
#
# Output: finetune/dpo_pairs/{domain}/dpo_{domain}_{stamp}.jsonl

set -euo pipefail
cd "$(dirname "$0")"

VENV="/ai/saisail/mascarade/venv_tuning/bin/activate"
if [ -f "${VENV}" ]; then
  # shellcheck source=/dev/null
  source "${VENV}"
else
  echo "[WARN] venv_tuning not found at ${VENV}, hoping Python deps are in PATH"
fi

N_CANDIDATES="${N_CANDIDATES:-8}"
DOMAINS_ALL="stm32 embedded spice kicad platformio iot dsp emc power freecad"

# Parse args
SELECTED_DOMAINS=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --domains) SELECTED_DOMAINS="${2//,/ }"; shift 2 ;;
    --n-candidates) N_CANDIDATES="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done
DOMAINS="${SELECTED_DOMAINS:-${DOMAINS_ALL}}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="runs/phase_b_${TIMESTAMP}"
mkdir -p "${LOG_DIR}"

echo "=========================================="
echo "Phase B — Rejection Sampling"
echo "Start:       $(date)"
echo "Domains:     ${DOMAINS}"
echo "Candidates:  ${N_CANDIDATES} per prompt"
echo "Log dir:     ${LOG_DIR}"
echo "=========================================="

# Warn on missing validators
command -v arm-none-eabi-gcc &>/dev/null || \
  echo "[WARN] arm-none-eabi-gcc not found — stm32/embedded validators may fall back"
command -v ngspice &>/dev/null || \
  echo "[WARN] ngspice not found — spice validator may fall back"
command -v kicad-cli &>/dev/null || \
  echo "[WARN] kicad-cli not found — kicad validator may fall back"

FAILED_DOMAINS=()

for domain in ${DOMAINS}; do
  echo ""
  echo ">>> [B] ${domain} — $(date)"
  if python rejection_sampling.py "${domain}" \
    --student-model "mascarade-${domain}" \
    --n-candidates "${N_CANDIDATES}" \
    --output-dir "dpo_pairs/${domain}" \
    2>&1 | tee "${LOG_DIR}/${domain}.log"; then
    echo ">>> [B] ${domain} OK"
  else
    echo ">>> [B] ${domain} FAILED (exit $?)"
    FAILED_DOMAINS+=("${domain}")
  fi
done

echo ""
echo "=========================================="
echo "Phase B COMPLETE — $(date)"
echo "DPO pairs:"
for domain in ${DOMAINS}; do
  files=$(ls "dpo_pairs/${domain}"/dpo_*.jsonl 2>/dev/null | wc -l || echo 0)
  pairs=$(cat "dpo_pairs/${domain}"/dpo_*.jsonl 2>/dev/null | wc -l || echo 0)
  echo "  ${domain}: ${files} file(s), ${pairs} pairs"
done
if [ ${#FAILED_DOMAINS[@]} -gt 0 ]; then
  echo "FAILED: ${FAILED_DOMAINS[*]}"
fi
echo "Next: ./batch_phase_c.sh"
echo "=========================================="
