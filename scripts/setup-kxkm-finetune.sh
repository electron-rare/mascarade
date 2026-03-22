#!/usr/bin/env bash
# Setup KXKM-AI GPU machine for mascarade finetune
# Target: kxkm@100.87.54.119, Ubuntu, RTX 4090, Python 3.12
# Run from grosmac: ./scripts/setup-kxkm-finetune.sh
set -euo pipefail

REMOTE="kxkm@100.87.54.119"
REMOTE_DIR="/ai/saisail/mascarade"
VENV_NAME=".venv-finetune"
REPO_URL="https://github.com/electron-rare/mascarade.git"
PYTHON_BIN="python3.12"

# ── Couleurs (respect NO_COLOR) ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m' DIM='\033[2m'
    RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[0;33m'
    CYAN='\033[0;36m' MAGENTA='\033[0;35m' NC='\033[0m'
else
    BOLD='' DIM='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' NC=''
fi

log()     { echo -e "  ${CYAN}▸${NC} $*"; }
ok()      { echo -e "  ${GREEN}✓${NC} $*"; }
warn()    { echo -e "  ${YELLOW}!${NC} $*"; }
err()     { echo -e "  ${RED}✗${NC} $*" >&2; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}$*${NC}"; echo -e "${DIM}  ──────────────────────────────────────────${NC}"; }
die()     { err "$@"; exit 1; }

# ── Resolve Mistral API key ──
MISTRAL_API_KEY="${MISTRAL_API_KEY:-}"
if [[ -z "$MISTRAL_API_KEY" ]]; then
    if [[ -t 0 ]]; then
        read -rsp "  Enter MISTRAL_API_KEY (hidden): " MISTRAL_API_KEY
        echo ""
    fi
fi
if [[ -z "$MISTRAL_API_KEY" ]]; then
    die "MISTRAL_API_KEY not set. Export it or provide interactively."
fi

# ── Helper: run command on remote ──
remote() {
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$REMOTE" "$@"
}

remote_script() {
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$REMOTE" bash -s
}

# ══════════════════════════════════════════════════════════════
section "1/8  SSH connectivity"
# ══════════════════════════════════════════════════════════════
log "Testing SSH to $REMOTE..."
if ! remote "echo ok" &>/dev/null; then
    die "Cannot reach $REMOTE via SSH. Check VPN / Tailscale / keys."
fi
ok "SSH connection OK"

# ══════════════════════════════════════════════════════════════
section "2/8  GPU verification"
# ══════════════════════════════════════════════════════════════
log "Running nvidia-smi..."
GPU_INFO=$(remote "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader" 2>/dev/null) \
    || die "nvidia-smi failed. Check NVIDIA drivers on $REMOTE."
ok "GPU detected: $GPU_INFO"

# ══════════════════════════════════════════════════════════════
section "3/8  Clone / update mascarade repo"
# ══════════════════════════════════════════════════════════════
log "Ensuring $REMOTE_DIR exists and is up to date..."
remote_script <<REMOTESH
set -euo pipefail
if [ ! -d "$REMOTE_DIR/.git" ]; then
    mkdir -p "$(dirname "$REMOTE_DIR")"
    git clone "$REPO_URL" "$REMOTE_DIR"
    echo "CLONED"
else
    cd "$REMOTE_DIR"
    git fetch origin
    git reset --hard origin/main
    echo "UPDATED"
fi
REMOTESH
ok "Repo ready at $REMOTE_DIR"

# ══════════════════════════════════════════════════════════════
section "4/8  Python venv"
# ══════════════════════════════════════════════════════════════
log "Creating venv with $PYTHON_BIN if needed..."
remote_script <<REMOTESH
set -euo pipefail
cd "$REMOTE_DIR"
if [ ! -d "$VENV_NAME/bin" ]; then
    $PYTHON_BIN -m venv "$VENV_NAME"
    echo "CREATED"
else
    echo "EXISTS"
fi
# Upgrade pip
source "$VENV_NAME/bin/activate"
pip install --upgrade pip setuptools wheel -q
echo "PIP_OK"
REMOTESH
ok "Venv $VENV_NAME ready"

# ══════════════════════════════════════════════════════════════
section "5/8  Install finetune dependencies"
# ══════════════════════════════════════════════════════════════
log "Installing PyTorch + finetune stack (this may take a while)..."
remote_script <<'REMOTESH'
set -euo pipefail
cd /ai/saisail/mascarade
source .venv-finetune/bin/activate

# PyTorch with CUDA 12.4 support
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu124 -q 2>&1 | tail -1

# Core finetune dependencies
pip install -q \
    "unsloth[cu124-ampere-torch250]" \
    trl \
    peft \
    "transformers>=4.45" \
    datasets \
    bitsandbytes \
    accelerate \
    safetensors \
    sentencepiece \
    protobuf \
    scipy \
    einops \
    flash-attn \
    wandb \
    huggingface_hub[cli] \
    2>&1 | tail -3

# kibot (KiCad finetune tooling)
pip install -q kibot 2>&1 | tail -1

# Project requirements if available
if [ -f finetune/requirements.txt ]; then
    pip install -q -r finetune/requirements.txt 2>&1 | tail -1
fi

echo "DEPS_INSTALLED"
REMOTESH
ok "Dependencies installed"

# ══════════════════════════════════════════════════════════════
section "6/8  Verify finetune scripts are executable"
# ══════════════════════════════════════════════════════════════
log "Checking script permissions..."
remote_script <<'REMOTESH'
set -euo pipefail
cd /ai/saisail/mascarade
SCRIPTS=(
    scripts/finetune-kicad.sh
    scripts/finetune-codestral.sh
    scripts/benchmark-finetune.sh
)
for s in "${SCRIPTS[@]}"; do
    if [ -f "$s" ]; then
        chmod +x "$s"
        echo "  +x $s"
    else
        echo "  MISSING $s"
    fi
done
# Ensure log directory exists
mkdir -p finetune/logs finetune/models finetune/checkpoints
echo "SCRIPTS_OK"
REMOTESH
ok "Scripts verified"

# ══════════════════════════════════════════════════════════════
section "7/8  Create .env with Mistral API key"
# ══════════════════════════════════════════════════════════════
log "Writing .env on remote..."
remote_script <<REMOTESH
set -euo pipefail
cd /ai/saisail/mascarade
cat > .env <<'ENVEOF'
# Mascarade finetune environment — auto-generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
MISTRAL_API_KEY=${MISTRAL_API_KEY}
HF_HOME=/ai/saisail/.cache/huggingface
TRANSFORMERS_CACHE=/ai/saisail/.cache/huggingface/hub
WANDB_PROJECT=mascarade-finetune
CUDA_VISIBLE_DEVICES=0
ENVEOF
chmod 600 .env
echo "ENV_OK"
REMOTESH
ok ".env written (600 permissions)"

# ══════════════════════════════════════════════════════════════
section "8/8  Smoke test (CUDA + model load)"
# ══════════════════════════════════════════════════════════════
log "Running smoke test on GPU..."
SMOKE_RESULT=$(remote_script <<'REMOTESH'
set -euo pipefail
cd /ai/saisail/mascarade
source .venv-finetune/bin/activate
python3 -c "
import torch
assert torch.cuda.is_available(), 'CUDA not available'
dev = torch.cuda.get_device_name(0)
mem = torch.cuda.get_device_properties(0).total_mem / 1e9
print(f'CUDA OK: {dev}, {mem:.1f} GB VRAM')

# Quick tensor test
t = torch.randn(1024, 1024, device='cuda')
r = torch.mm(t, t)
print(f'MATMUL OK: {r.shape}')

# Verify key imports
import transformers, peft, trl, datasets, bitsandbytes
print(f'IMPORTS OK: transformers={transformers.__version__}, peft={peft.__version__}')
print('SMOKE_PASS')
"
REMOTESH
)
echo "$SMOKE_RESULT" | while IFS= read -r line; do log "$line"; done

if echo "$SMOKE_RESULT" | grep -q "SMOKE_PASS"; then
    ok "Smoke test passed"
else
    die "Smoke test FAILED. Check output above."
fi

# ══════════════════════════════════════════════════════════════
section "Setup complete"
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "  ${GREEN}${BOLD}KXKM-AI finetune environment is ready${NC}"
echo ""
echo -e "  ${DIM}Machine:${NC}    $REMOTE"
echo -e "  ${DIM}Repo:${NC}       $REMOTE_DIR"
echo -e "  ${DIM}Venv:${NC}       $REMOTE_DIR/$VENV_NAME"
echo -e "  ${DIM}GPU:${NC}        $GPU_INFO"
echo -e "  ${DIM}Logs dir:${NC}   $REMOTE_DIR/finetune/logs/"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo -e "    ${CYAN}1.${NC} Run KiCad finetune:     ./scripts/run-finetune-remote.sh kicad"
echo -e "    ${CYAN}2.${NC} Run Codestral finetune:  ./scripts/run-finetune-remote.sh codestral"
echo -e "    ${CYAN}3.${NC} Run benchmark:           ./scripts/run-finetune-remote.sh benchmark"
echo -e "    ${CYAN}4.${NC} Attach to running job:   ssh -t $REMOTE 'tmux attach -t finetune'"
echo ""
