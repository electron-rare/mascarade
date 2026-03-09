#!/usr/bin/env bash
#
# Train domains in parallel on CPU.
# Splits domains into waves that fit in available RAM.
#
# Usage:
#   ./train_parallel.sh                           # Train remaining domains (serial by default)
#   ./train_parallel.sh --domains power,dsp,emc  # Specific domains
#   MASCARADE_ALLOW_PARALLEL_CPU=1 ./train_parallel.sh --parallel 3
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${SCRIPT_DIR}/.venv/bin/activate"
VENV_FALLBACK="${SCRIPT_DIR}/../core/.venv/bin/activate"
LOG_DIR="${SCRIPT_DIR}/logs"
DATASETS_DIR="${SCRIPT_DIR}/datasets"

MODEL="Qwen/Qwen2.5-Coder-1.5B-Instruct"
# Use model_selector choice if available
_SEL_FILE="${SCRIPT_DIR}/selected_model.json"
if [[ -f "$_SEL_FILE" ]]; then
    _sel=$(python3 -c "import json; print(json.load(open('$_SEL_FILE'))['model_id'])" 2>/dev/null)
    [[ -n "$_sel" ]] && MODEL="$_sel"
fi
SEQ_LEN=512
EPOCHS=2
MAX_SAMPLES=500
MAX_PARALLEL=1
SELECTED_DOMAINS=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

while [[ $# -gt 0 ]]; do
    case $1 in
        --domains) SELECTED_DOMAINS="${2//,/ }"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --seq-len) SEQ_LEN="$2"; shift 2 ;;
        --epochs) EPOCHS="$2"; shift 2 ;;
        --max-samples) MAX_SAMPLES="$2"; shift 2 ;;
        --parallel) MAX_PARALLEL="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--domains d1,d2] [--parallel N] [--max-samples N]"
            echo "By default CPU training is serialized on this machine."
            echo "Set MASCARADE_ALLOW_PARALLEL_CPU=1 to allow --parallel > 1."
            exit 0 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

if [[ "$MAX_PARALLEL" -gt 1 && "${MASCARADE_ALLOW_PARALLEL_CPU:-0}" != "1" ]]; then
    echo "Parallel CPU training above 1 is disabled by default on this machine." >&2
    echo "Set MASCARADE_ALLOW_PARALLEL_CPU=1 to override intentionally." >&2
    exit 1
fi

# Activate venv
if [[ -f "$VENV" ]]; then
    source "$VENV"
elif [[ -f "$VENV_FALLBACK" ]]; then
    source "$VENV_FALLBACK"
fi

mkdir -p "$LOG_DIR"

# Determine domains to train (skip those with existing adapters)
ALL_DOMAINS="stm32 spice iot power dsp emc kicad embedded platformio freecad"
if [[ -n "$SELECTED_DOMAINS" ]]; then
    DOMAINS_TO_CHECK="$SELECTED_DOMAINS"
else
    DOMAINS_TO_CHECK="$ALL_DOMAINS"
fi

DOMAINS=()
SKIPPED=()
for d in $DOMAINS_TO_CHECK; do
    dataset="${DATASETS_DIR}/${d}_chat.jsonl"
    adapter="${SCRIPT_DIR}/models_local/${d}/adapter"
    if [[ ! -f "$dataset" ]]; then
        SKIPPED+=("$d (no dataset)")
    elif [[ -d "$adapter" ]]; then
        SKIPPED+=("$d (already trained)")
    else
        DOMAINS+=("$d")
    fi
done

TOTAL=${#DOMAINS[@]}

echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║         MASCARADE Parallel CPU Training                 ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${BOLD}Model:${NC}      $MODEL"
echo -e "  ${BOLD}Seq len:${NC}    $SEQ_LEN"
echo -e "  ${BOLD}Epochs:${NC}     $EPOCHS"
echo -e "  ${BOLD}Samples:${NC}    $MAX_SAMPLES"
echo -e "  ${BOLD}Parallel:${NC}   $MAX_PARALLEL"
echo -e "  ${BOLD}To train:${NC}   $TOTAL"

if [[ ${#SKIPPED[@]} -gt 0 ]]; then
    echo -e "  ${DIM}Skipped:${NC}    ${SKIPPED[*]}"
fi
echo ""

if [[ $TOTAL -eq 0 ]]; then
    echo -e "  ${YELLOW}Nothing to train. All domains already have adapters.${NC}"
    exit 0
fi

# Launch function for one domain
train_one() {
    local domain=$1
    local log_file="${LOG_DIR}/${domain}_parallel_$(date +%Y%m%d_%H%M%S).log"

    echo -e "  ${CYAN}START${NC} ${domain} → ${DIM}${log_file}${NC}"

    # Limit threads per process to share CPU fairly
    local threads=$(( $(nproc) / MAX_PARALLEL ))
    [[ $threads -lt 1 ]] && threads=1

    CUDA_VISIBLE_DEVICES="" \
    OMP_NUM_THREADS=$threads \
    MKL_NUM_THREADS=$threads \
    OPENBLAS_NUM_THREADS=$threads \
    python "${SCRIPT_DIR}/train_cpu.py" \
        "$domain" \
        --model "$MODEL" \
        --seq-len "$SEQ_LEN" \
        --epochs "$EPOCHS" \
        --max-samples "$MAX_SAMPLES" \
        --eval \
        > "$log_file" 2>&1

    local rc=$?
    if [[ $rc -eq 0 ]]; then
        local loss=$(grep "Training loss:" "$log_file" | tail -1 | awk '{print $NF}')
        echo -e "  ${GREEN}DONE${NC}  ${domain}  loss=${loss}"
    else
        echo -e "  ${RED}FAIL${NC}  ${domain}  (exit $rc) — see ${log_file}"
    fi
    return $rc
}

export -f train_one
export SCRIPT_DIR LOG_DIR MAX_PARALLEL MODEL SEQ_LEN EPOCHS MAX_SAMPLES
export RED GREEN YELLOW CYAN BOLD DIM NC

# Run in waves
START_TIME=$(date +%s)
echo -e "\n${BOLD}Training ${TOTAL} domains, ${MAX_PARALLEL} at a time...${NC}\n"

COMPLETED=0
FAILED=0
PIDS=()
DOMAIN_MAP=()

launch_next() {
    local idx=$1
    if [[ $idx -lt $TOTAL ]]; then
        local domain="${DOMAINS[$idx]}"
        train_one "$domain" &
        PIDS+=($!)
        DOMAIN_MAP+=("$domain")
    fi
}

# Launch initial wave
for (( i=0; i<MAX_PARALLEL && i<TOTAL; i++ )); do
    launch_next $i
done

NEXT_IDX=$MAX_PARALLEL

# Wait for completions and launch next
while [[ ${#PIDS[@]} -gt 0 ]]; do
    NEW_PIDS=()
    NEW_DOMAIN_MAP=()
    for j in "${!PIDS[@]}"; do
        pid="${PIDS[$j]}"
        domain="${DOMAIN_MAP[$j]}"
        if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid" 2>/dev/null
            rc=$?
            if [[ $rc -eq 0 ]]; then
                COMPLETED=$((COMPLETED + 1))
            else
                FAILED=$((FAILED + 1))
            fi
            # Launch next if available
            if [[ $NEXT_IDX -lt $TOTAL ]]; then
                launch_next $NEXT_IDX
                NEW_PIDS+=($!)
                NEW_DOMAIN_MAP+=("${DOMAINS[$NEXT_IDX]}")
                NEXT_IDX=$((NEXT_IDX + 1))
            fi
        else
            NEW_PIDS+=("$pid")
            NEW_DOMAIN_MAP+=("$domain")
        fi
    done
    PIDS=("${NEW_PIDS[@]+"${NEW_PIDS[@]}"}")
    DOMAIN_MAP=("${NEW_DOMAIN_MAP[@]+"${NEW_DOMAIN_MAP[@]}"}")
    sleep 10
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║              Parallel Training Complete                 ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${GREEN}Completed: ${COMPLETED}${NC}  ${RED}Failed: ${FAILED}${NC}"
printf "  ${BOLD}Total time: %dh%02dm%02ds${NC}\n" $((DURATION/3600)) $(((DURATION%3600)/60)) $((DURATION%60))
echo ""

# Show results
echo -e "  ${BOLD}Adapters:${NC}"
for d in "${DOMAINS[@]}"; do
    adapter="${SCRIPT_DIR}/models_local/${d}/adapter"
    if [[ -d "$adapter" ]]; then
        size=$(du -sh "$adapter" 2>/dev/null | cut -f1)
        log=$(ls -t "${LOG_DIR}/${d}_parallel_"*.log 2>/dev/null | head -1)
        loss=$(grep "Training loss:" "$log" 2>/dev/null | tail -1 | awk '{print $NF}')
        echo -e "    ${GREEN}${d}${NC} → ${adapter} (${size}) loss=${loss:-?}"
    else
        echo -e "    ${RED}${d}${NC} — no adapter"
    fi
done
echo ""
echo -e "  ${DIM}Logs: ${LOG_DIR}/${NC}"
