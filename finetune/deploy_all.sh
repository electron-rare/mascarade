#!/usr/bin/env bash
#
# Deploy all trained adapters: merge → GGUF → Ollama
#
# Usage:
#   ./deploy_all.sh                  # All domains with adapters
#   ./deploy_all.sh --domains stm32,kicad
#   ./deploy_all.sh --step merge     # Only merge step
#   ./deploy_all.sh --dry-run
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${SCRIPT_DIR}/.venv/bin/activate"
VENV_FALLBACK="${SCRIPT_DIR}/../core/.venv/bin/activate"
MODELS_DIR="${SCRIPT_DIR}/models_local"

ALL_DOMAINS="stm32 spice iot power dsp emc kicad embedded platformio freecad"
SELECTED_DOMAINS=""
STEP=""
DRY_RUN=false

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
        --step) STEP="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--domains d1,d2] [--step merge|gguf|deploy] [--dry-run]"
            exit 0 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

DOMAINS="${SELECTED_DOMAINS:-$ALL_DOMAINS}"

# Activate venv
if [[ -f "$VENV" ]]; then
    source "$VENV"
elif [[ -f "$VENV_FALLBACK" ]]; then
    source "$VENV_FALLBACK"
fi

echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║           MASCARADE Deployment Pipeline                 ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Find domains with trained adapters
READY=()
SKIP=()
for domain in $DOMAINS; do
    adapter="${MODELS_DIR}/${domain}/adapter"
    if [[ -d "$adapter" ]]; then
        READY+=("$domain")
        info="${MODELS_DIR}/${domain}/training_info.json"
        loss=""
        if [[ -f "$info" ]]; then
            loss=$(python3 -c "import json; print(f'{json.load(open(\"$info\"))[\"loss\"]:.4f}')" 2>/dev/null || echo "?")
        fi
        echo -e "  ${GREEN}✓${NC} $(printf '%-14s' "$domain")  adapter ready  loss=$loss"
    else
        SKIP+=("$domain")
        echo -e "  ${YELLOW}·${NC} $(printf '%-14s' "$domain")  no adapter"
    fi
done
echo ""

if [[ ${#READY[@]} -eq 0 ]]; then
    echo -e "  ${RED}No trained adapters found. Run train_all.sh first.${NC}"
    exit 1
fi

echo -e "  ${BOLD}Ready: ${#READY[@]}${NC}  ${DIM}Skipped: ${#SKIP[@]}${NC}"

STEPS="merge,gguf,deploy"
if [[ -n "$STEP" ]]; then
    STEPS="$STEP"
fi
echo -e "  ${BOLD}Steps:${NC} $STEPS"
echo ""

if $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY RUN] Would deploy ${#READY[@]} domains. Exiting.${NC}"
    exit 0
fi

# Deploy each domain
COMPLETED=0
FAILED=0
for domain in "${READY[@]}"; do
    echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  Deploying ${CYAN}${BOLD}${domain}${NC} (steps: ${STEPS})"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    IFS=',' read -ra STEP_LIST <<< "$STEPS"
    domain_ok=true
    for s in "${STEP_LIST[@]}"; do
        echo -e "\n  ${BOLD}[${s}]${NC} ${domain}..."
        set +e
        python "${SCRIPT_DIR}/pipeline.py" "$domain" --step "$s" 2>&1
        rc=$?
        set -e
        if [[ $rc -ne 0 ]]; then
            echo -e "  ${RED}FAILED${NC} step $s for $domain (exit $rc)"
            domain_ok=false
            break
        fi
    done

    if $domain_ok; then
        COMPLETED=$((COMPLETED + 1))
        echo -e "\n  ${GREEN}${BOLD}DEPLOYED${NC} ${domain}"
    else
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║                 Deployment Complete                     ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${GREEN}Deployed: ${COMPLETED}${NC}  ${RED}Failed: ${FAILED}${NC}"
echo ""

# List Ollama models
echo -e "  ${BOLD}Ollama models:${NC}"
curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for m in data.get('models', []):
    if 'mascarade' in m['name']:
        size = m['size'] / 1024**3
        print(f\"    {m['name']:30s}  {size:.1f} GB\")
" 2>/dev/null || echo "    (couldn't query Ollama)"
echo ""
