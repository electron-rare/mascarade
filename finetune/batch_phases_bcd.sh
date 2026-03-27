#!/bin/bash
# Phases B→C→D chained — runs after Phase A SFT completes.
# Executes rejection sampling, DPO training, then deploy + HF upload.
#
# Usage (on KXKM-AI, after Phase A is done):
#   ./batch_phases_bcd.sh
#   ./batch_phases_bcd.sh --domains stm32,kicad
#   ./batch_phases_bcd.sh --skip-phase-d   # stop before HF upload

set -euo pipefail
cd "$(dirname "$0")"

SKIP_D=false
EXTRA_DOMAINS=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --domains) EXTRA_DOMAINS="--domains $2"; shift 2 ;;
    --skip-phase-d) SKIP_D=true; shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "Phases B→C→D chain — Start: $(date)"
echo "=========================================="

echo ""
echo "===== PHASE B: Rejection Sampling ====="
# shellcheck disable=SC2086
./batch_phase_b.sh ${EXTRA_DOMAINS}

echo ""
echo "===== PHASE C: DPO/ORPO Training ====="
# shellcheck disable=SC2086
./batch_phase_c.sh ${EXTRA_DOMAINS}

if [ "${SKIP_D}" = false ]; then
  echo ""
  echo "===== PHASE D: Deploy + HF Upload ====="
  # shellcheck disable=SC2086
  ./batch_phase_d.sh ${EXTRA_DOMAINS}
fi

echo ""
echo "=========================================="
echo "Phases B→C→D COMPLETE — $(date)"
echo "=========================================="
