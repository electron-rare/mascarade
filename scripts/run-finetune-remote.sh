#!/usr/bin/env bash
# Run finetune job on KXKM-AI from grosmac
# Usage: ./run-finetune-remote.sh [kicad|codestral|benchmark]
set -euo pipefail

REMOTE="kxkm@100.87.54.119"
REMOTE_DIR="/ai/saisail/mascarade"
SESSION="finetune"
JOB="${1:-}"

# ── Couleurs (respect NO_COLOR) ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m' DIM='\033[2m'
    RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[0;33m'
    CYAN='\033[0;36m' MAGENTA='\033[0;35m' NC='\033[0m'
else
    BOLD='' DIM='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' NC=''
fi

log()  { echo -e "  ${CYAN}▸${NC} $*"; }
ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
err()  { echo -e "  ${RED}✗${NC} $*" >&2; }
die()  { err "$@"; exit 1; }

usage() {
    echo -e "  ${BOLD}Usage:${NC} $0 <job> [--attach] [--dry-run]"
    echo ""
    echo -e "  ${BOLD}Jobs:${NC}"
    echo -e "    kicad       Fine-tune Mistral Small on KiCad dataset"
    echo -e "    codestral   Fine-tune Codestral on embedded code"
    echo -e "    benchmark   Run base vs fine-tuned benchmark"
    echo ""
    echo -e "  ${BOLD}Options:${NC}"
    echo -e "    --attach    Attach to tmux session after starting"
    echo -e "    --dry-run   Show command without executing"
    echo ""
    echo -e "  ${BOLD}Examples:${NC}"
    echo -e "    $0 kicad"
    echo -e "    $0 codestral --attach"
    echo -e "    $0 benchmark --dry-run"
    exit 1
}

# ── Parse arguments ──
ATTACH=false
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --attach)  ATTACH=true ;;
        --dry-run) DRY_RUN=true ;;
        -h|--help) usage ;;
        -*)        die "Unknown option: $arg" ;;
    esac
done

[[ -z "$JOB" ]] && usage

# ── Map job to script ──
case "$JOB" in
    kicad)     SCRIPT="scripts/finetune-kicad.sh" ;;
    codestral) SCRIPT="scripts/finetune-codestral.sh" ;;
    benchmark) SCRIPT="scripts/benchmark-finetune.sh" ;;
    *)         die "Unknown job: $JOB"; usage ;;
esac

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOGFILE="finetune/logs/${TIMESTAMP}-${JOB}.log"

# ── Build remote command ──
REMOTE_CMD="cd $REMOTE_DIR && source .venv-finetune/bin/activate && source .env 2>/dev/null; mkdir -p finetune/logs && ./$SCRIPT 2>&1 | tee $LOGFILE; echo ''; echo 'Job finished at $(date). Press enter to close.'; read"

log "Job:      $JOB"
log "Script:   $SCRIPT"
log "Remote:   $REMOTE:$REMOTE_DIR"
log "Log:      $LOGFILE"
log "Session:  tmux/$SESSION"
echo ""

if $DRY_RUN; then
    echo -e "  ${YELLOW}[dry-run]${NC} Would execute on $REMOTE:"
    echo "    tmux new-session -d -s $SESSION '$REMOTE_CMD'"
    exit 0
fi

# ── Check for existing tmux session ──
if ssh -o ConnectTimeout=10 "$REMOTE" "tmux has-session -t $SESSION 2>/dev/null"; then
    warn "tmux session '$SESSION' already exists on $REMOTE"
    echo -e "  ${DIM}Attach:${NC}  ssh -t $REMOTE 'tmux attach -t $SESSION'"
    echo -e "  ${DIM}Kill:${NC}    ssh $REMOTE 'tmux kill-session -t $SESSION'"
    echo ""
    read -rp "  Kill existing session and start new? [y/N] " answer
    if [[ "${answer,,}" == "y" ]]; then
        ssh "$REMOTE" "tmux kill-session -t $SESSION"
        ok "Previous session killed"
    else
        log "Aborted. Attach with: ssh -t $REMOTE 'tmux attach -t $SESSION'"
        exit 0
    fi
fi

# ── Launch ──
log "Starting finetune job..."
ssh -o ConnectTimeout=10 "$REMOTE" "tmux new-session -d -s $SESSION '${REMOTE_CMD}'"
ok "Job started in tmux session '$SESSION' on $REMOTE"
echo ""
echo -e "  ${BOLD}Monitor:${NC}"
echo -e "    ${CYAN}Attach:${NC}   ssh -t $REMOTE 'tmux attach -t $SESSION'"
echo -e "    ${CYAN}Tail log:${NC} ssh $REMOTE 'tail -f $REMOTE_DIR/$LOGFILE'"
echo -e "    ${CYAN}GPU:${NC}      ssh $REMOTE 'nvidia-smi'"
echo -e "    ${CYAN}Kill:${NC}     ssh $REMOTE 'tmux kill-session -t $SESSION'"
echo ""

if $ATTACH; then
    log "Attaching to session..."
    exec ssh -t "$REMOTE" "tmux attach -t $SESSION"
fi
