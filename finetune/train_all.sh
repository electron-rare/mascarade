#!/usr/bin/env bash
#
# Train all domains in batch with progress dashboard.
#
# Usage:
#   ./train_all.sh                    # All domains, GPU (Qwen2.5-Coder-1.5B)
#   ./train_all.sh --domains spice,kicad,stm32
#   ./train_all.sh --model Qwen/Qwen2.5-Coder-1.5B-Instruct --cpu
#   ./train_all.sh --dry-run          # Show what would run
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${SCRIPT_DIR}/.venv/bin/activate"
VENV_FALLBACK="${SCRIPT_DIR}/../core/.venv/bin/activate"
LOG_DIR="${SCRIPT_DIR}/logs"
DATASETS_DIR="${SCRIPT_DIR}/datasets"

ALL_DOMAINS="stm32 spice iot power dsp emc kicad embedded platformio freecad"
DEFAULT_GPU_MODEL="Qwen/Qwen2.5-Coder-1.5B-Instruct"
DEFAULT_CPU_MODEL="$DEFAULT_GPU_MODEL"
# Use model_selector choice if available
SELECTED_MODEL_FILE="${SCRIPT_DIR}/selected_model.json"
if [[ -f "$SELECTED_MODEL_FILE" ]]; then
    _sel=$(python3 -c "import json; print(json.load(open('$SELECTED_MODEL_FILE'))['model_id'])" 2>/dev/null)
    if [[ -n "$_sel" ]]; then
        DEFAULT_GPU_MODEL="$_sel"
        DEFAULT_CPU_MODEL="$_sel"
    fi
fi
MODEL="$DEFAULT_GPU_MODEL"
SEQ_LEN=1024
EPOCHS=2
MAX_SAMPLES=""
USE_CPU=false
DRY_RUN=false
SELECTED_DOMAINS=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --domains DOMAIN1,DOMAIN2   Comma-separated domains (default: all)"
    echo "  --model MODEL_NAME          HuggingFace model (default: $MODEL)"
    echo "  --seq-len N                 Max sequence length (default: $SEQ_LEN)"
    echo "  --epochs N                  Training epochs (default: $EPOCHS)"
    echo "  --max-samples N             Max samples per domain"
    echo "  --cpu                       Use CPU training (slower, no VRAM limit)"
    echo "  --dry-run                   Show plan without executing"
    echo "  -h, --help                  Show this help"
    exit 0
}

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --domains) SELECTED_DOMAINS="${2//,/ }"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --seq-len) SEQ_LEN="$2"; shift 2 ;;
        --epochs) EPOCHS="$2"; shift 2 ;;
        --max-samples) MAX_SAMPLES="$2"; shift 2 ;;
        --cpu) USE_CPU=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

if $USE_CPU && [[ "$MODEL" == "$DEFAULT_GPU_MODEL" ]]; then
    MODEL="$DEFAULT_CPU_MODEL"
fi

DOMAINS="${SELECTED_DOMAINS:-$ALL_DOMAINS}"
DOMAIN_LIST=($DOMAINS)
TOTAL=${#DOMAIN_LIST[@]}

mkdir -p "$LOG_DIR"

# --- Dashboard functions ---

bar() {
    local pct=$1 width=30
    local filled=$((pct * width / 100))
    local empty=$((width - filled))
    printf '['
    printf '%0.s#' $(seq 1 $filled 2>/dev/null) || true
    printf '%0.s-' $(seq 1 $empty 2>/dev/null) || true
    printf '] %3d%%' "$pct"
}

timestamp() {
    date '+%H:%M:%S'
}

elapsed() {
    local secs=$1
    printf '%dh%02dm%02ds' $((secs/3600)) $(((secs%3600)/60)) $((secs%60))
}

dataset_size() {
    local domain=$1
    local f="${DATASETS_DIR}/${domain}_chat.jsonl"
    if [[ -f "$f" ]]; then
        wc -l < "$f"
    else
        echo "0"
    fi
}

# --- Header ---
clear
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║           MASCARADE Fine-Tuning Pipeline                ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${BOLD}Model:${NC}    $MODEL"
echo -e "  ${BOLD}Seq len:${NC}  $SEQ_LEN"
echo -e "  ${BOLD}Epochs:${NC}   $EPOCHS"
echo -e "  ${BOLD}Device:${NC}   $(if $USE_CPU; then echo 'CPU'; else echo 'GPU'; fi)"
echo -e "  ${BOLD}Domains:${NC}  $TOTAL"
echo ""

# --- Domain table ---
echo -e "  ${BOLD}${BLUE}Domain          Dataset   Status${NC}"
echo -e "  ${DIM}──────────────  ────────  ──────────────────${NC}"
for domain in "${DOMAIN_LIST[@]}"; do
    count=$(dataset_size "$domain")
    if [[ "$count" -eq 0 ]]; then
        echo -e "  ${YELLOW}$(printf '%-14s' "$domain")  $(printf '%6s' "$count")    SKIP (no dataset)${NC}"
    else
        echo -e "  $(printf '%-14s' "$domain")  $(printf '%6s' "$count")    $(bar 0)"
    fi
done
echo ""

if $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY RUN] Would train ${TOTAL} domains. Exiting.${NC}"
    exit 0
fi

# --- Training loop ---
TRAIN_SCRIPT="train_local.py"
if $USE_CPU; then
    TRAIN_SCRIPT="train_cpu.py"
fi

declare -A STATUS
declare -A DURATIONS
START_GLOBAL=$(date +%s)
COMPLETED=0
FAILED=0
SKIPPED=0

for i in "${!DOMAIN_LIST[@]}"; do
    domain="${DOMAIN_LIST[$i]}"
    idx=$((i + 1))
    count=$(dataset_size "$domain")

    echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${BOLD}[${idx}/${TOTAL}]${NC} Training ${CYAN}${BOLD}${domain}${NC} (${count} examples)"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [[ "$count" -eq 0 ]]; then
        echo -e "  ${YELLOW}SKIPPED${NC} — no dataset file"
        STATUS[$domain]="SKIP"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    log_file="${LOG_DIR}/${domain}_$(date +%Y%m%d_%H%M%S).log"
    start_time=$(date +%s)

    # Build command
    cmd="python ${SCRIPT_DIR}/${TRAIN_SCRIPT} ${domain} --eval --seq-len ${SEQ_LEN} --epochs ${EPOCHS}"
    if [[ -n "$MAX_SAMPLES" ]]; then
        cmd="${cmd} --max-samples ${MAX_SAMPLES}"
    fi
    cmd="${cmd} --model ${MODEL}"

    echo -e "  ${DIM}$ ${cmd}${NC}"
    echo -e "  ${DIM}Log: ${log_file}${NC}"
    echo ""

    # Run training with live output + log
    set +e
    if [[ -f "$VENV" ]]; then
        source "$VENV" 2>/dev/null
    elif [[ -f "$VENV_FALLBACK" ]]; then
        source "$VENV_FALLBACK" 2>/dev/null
    fi
    $cmd 2>&1 | tee "$log_file"
    exit_code=${PIPESTATUS[0]}
    set -e

    end_time=$(date +%s)
    duration=$((end_time - start_time))
    DURATIONS[$domain]=$duration

    if [[ $exit_code -eq 0 ]]; then
        STATUS[$domain]="OK"
        COMPLETED=$((COMPLETED + 1))
        echo -e "\n  ${GREEN}${BOLD}DONE${NC} ${domain} in $(elapsed $duration)"
    else
        STATUS[$domain]="FAIL"
        FAILED=$((FAILED + 1))
        echo -e "\n  ${RED}${BOLD}FAILED${NC} ${domain} (exit $exit_code) after $(elapsed $duration)"
    fi
done

# --- Summary ---
END_GLOBAL=$(date +%s)
TOTAL_TIME=$((END_GLOBAL - START_GLOBAL))

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║                   Training Complete                     ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "  ${BOLD}Results:${NC}"
echo -e "  ${DIM}──────────────  ────────  ──────────${NC}"
for domain in "${DOMAIN_LIST[@]}"; do
    status="${STATUS[$domain]:-?}"
    dur="${DURATIONS[$domain]:-0}"
    case "$status" in
        OK)   color="$GREEN" ;;
        FAIL) color="$RED" ;;
        SKIP) color="$YELLOW" ;;
        *)    color="$NC" ;;
    esac
    echo -e "  $(printf '%-14s' "$domain")  ${color}${BOLD}$(printf '%-6s' "$status")${NC}  $(elapsed "$dur")"
done

echo ""
echo -e "  ${GREEN}Completed: ${COMPLETED}${NC}  ${RED}Failed: ${FAILED}${NC}  ${YELLOW}Skipped: ${SKIPPED}${NC}"
echo -e "  ${BOLD}Total time: $(elapsed $TOTAL_TIME)${NC}"
echo ""

# List generated adapters
echo -e "  ${BOLD}Adapters:${NC}"
for domain in "${DOMAIN_LIST[@]}"; do
    adapter="${SCRIPT_DIR}/models_local/${domain}/adapter"
    if [[ -d "$adapter" ]]; then
        size=$(du -sh "$adapter" 2>/dev/null | cut -f1)
        echo -e "    ${GREEN}$domain${NC} → $adapter ($size)"
    fi
done

echo ""
echo -e "  ${DIM}Logs: ${LOG_DIR}/${NC}"
echo -e "  ${DIM}Next: python pipeline.py <domain> --steps merge,gguf,deploy${NC}"
