#!/usr/bin/env bash
# weekly_dataset_refresh.sh — Refresh all domain datasets and optionally upload to HF
#
# Wraps finetune/dataset_refresh.py for all 11 canonical domains.
# Designed to run as a weekly cron job on the KXKM-AI machine.
#
# Usage:
#   ./scripts/weekly_dataset_refresh.sh                # refresh all domains
#   ./scripts/weekly_dataset_refresh.sh --upload       # refresh + push to HF Hub
#   ./scripts/weekly_dataset_refresh.sh --domains stm32,kicad --upload
#   ./scripts/weekly_dataset_refresh.sh --dry-run      # quality check only
#
# Cron example (every Sunday 3am):
#   0 3 * * 0 /path/to/mascarade/scripts/weekly_dataset_refresh.sh --upload >> /var/log/mascarade/dataset_refresh.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FINETUNE_DIR="$(dirname "$SCRIPT_DIR")/finetune"
REFRESH_SCRIPT="${FINETUNE_DIR}/dataset_refresh.py"
UPLOAD_SCRIPT="${FINETUNE_DIR}/upload_datasets_hf.sh"
LOG_DIR="${SCRIPT_DIR}/../finetune/runs/refresh_$(date +%Y%m%d_%H%M%S)"

ALL_DOMAINS="stm32 spice iot power dsp emc kicad embedded platformio freecad components"

# ── Arg parsing ──────────────────────────────────────────────────────────────
DO_UPLOAD=0
DRY_RUN=0
DOMAINS="$ALL_DOMAINS"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --upload)       DO_UPLOAD=1; shift ;;
        --dry-run)      DRY_RUN=1; shift ;;
        --domains)      shift; DOMAINS="${1//,/ }"; shift ;;
        -h|--help)
            echo "Usage: $0 [--upload] [--dry-run] [--domains d1,d2,...]"
            exit 0
            ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Setup ─────────────────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/refresh.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== Weekly Dataset Refresh — $(date '+%Y-%m-%d %H:%M:%S') ==="
log "Domains: $DOMAINS"
[[ $DO_UPLOAD -eq 1 ]] && log "Mode: refresh + HF upload" || log "Mode: refresh only"
[[ $DRY_RUN -eq 1 ]] && log "Dry-run: quality check only, no dataset write"

if [[ ! -f "$REFRESH_SCRIPT" ]]; then
    log "ERROR: $REFRESH_SCRIPT not found. Run from mascarade repo root."
    exit 1
fi

# ── Refresh each domain ───────────────────────────────────────────────────────
FAILED=()
SUCCESS=()

for domain in $DOMAINS; do
    log ""
    log "── Refreshing domain: $domain ──"

    refresh_args=("$domain")
    [[ $DRY_RUN -eq 1 ]] && refresh_args+=("--quality-only")

    if python3 "$REFRESH_SCRIPT" "${refresh_args[@]}" >> "$LOG_FILE" 2>&1; then
        log "[OK] $domain refresh complete"
        SUCCESS+=("$domain")
    else
        log "[FAIL] $domain refresh failed (exit code $?)"
        FAILED+=("$domain")
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
log ""
log "=== Refresh Summary ==="
log "Success: ${#SUCCESS[@]} domains — ${SUCCESS[*]:-none}"
log "Failed:  ${#FAILED[@]} domains — ${FAILED[*]:-none}"

if [[ ${#FAILED[@]} -gt 0 ]]; then
    log "WARNING: Some domains failed. Check $LOG_FILE for details."
fi

# ── Optional HF upload ────────────────────────────────────────────────────────
if [[ $DO_UPLOAD -eq 1 && $DRY_RUN -eq 0 ]]; then
    log ""
    log "=== HF Upload ==="
    if [[ ${#SUCCESS[@]} -eq 0 ]]; then
        log "No successful domains to upload."
    else
        export DOMAINS_FILTER="${SUCCESS[*]}"
        if bash "$UPLOAD_SCRIPT" >> "$LOG_FILE" 2>&1; then
            log "[OK] HF upload complete"
        else
            log "[FAIL] HF upload failed. Check $LOG_FILE"
            exit 1
        fi
    fi
fi

log ""
log "Log saved to: $LOG_FILE"

if [[ ${#FAILED[@]} -gt 0 ]]; then
    exit 1
fi
