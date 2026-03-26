#!/usr/bin/env bash
# deploy-to-photon.sh — Deploy best finetuned models to photon (production)
# Copies selected models, configures mascarade core ML router, restarts, health-checks
#
# Usage: ./scripts/deploy-to-photon.sh [--model MODEL] [--all] [--dry-run] [--skip-restart]
#
# By default reads BENCHMARK_V4_REPORT.md to pick the best model per domain.
# Use --model to deploy a specific model, or --all for all available models.
#
# Requires:
#   - SSH access to root@192.168.0.119 (photon)
#   - SSH access to kxkm@100.87.54.119 (KXKM-AI, source of models)

set -euo pipefail

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────
KXKM_HOST="${KXKM_HOST:-kxkm@100.87.54.119}"
KXKM_DIR="/ai/saisail/mascarade"
KXKM_RUNS="${KXKM_DIR}/finetune/runs"

PHOTON_HOST="${PHOTON_HOST:-root@192.168.0.119}"
PHOTON_DIR="/mascarade"
PHOTON_MODELS_DIR="/mascarade/models/finetuned"
PHOTON_CORE_CONFIG="${PHOTON_DIR}/core/config/ml_router.yaml"
PHOTON_SERVICE="mascarade-core"

OLLAMA_PORT="${OLLAMA_PORT:-11434}"
REPORT_FILE="BENCHMARK_V4_REPORT.md"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Couleurs ──
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    BOLD='\033[1m' DIM='\033[2m'
    RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[0;33m'
    CYAN='\033[0;36m' MAGENTA='\033[0;35m' NC='\033[0m'
else
    BOLD='' DIM='' RED='' GREEN='' YELLOW='' CYAN='' MAGENTA='' NC=''
fi

log()     { echo -e "  ${CYAN}>>>${NC} $*"; }
ok()      { echo -e "  ${GREEN}[ok]${NC} $*"; }
warn()    { echo -e "  ${YELLOW}[warn]${NC} $*"; }
err()     { echo -e "  ${RED}[err]${NC} $*" >&2; }
die()     { err "$@"; exit 1; }
section() { echo ""; echo -e "  ${MAGENTA}${BOLD}=== $* ===${NC}"; }

# ── Parse arguments ──
DRY_RUN=false
SKIP_RESTART=false
DEPLOY_ALL=false
SPECIFIC_MODEL=""

for arg in "$@"; do
    case "$arg" in
        --dry-run)       DRY_RUN=true ;;
        --skip-restart)  SKIP_RESTART=true ;;
        --all)           DEPLOY_ALL=true ;;
        --model=*)       SPECIFIC_MODEL="${arg#--model=}" ;;
        --model)         shift_next=true ;;  # handled below
        -h|--help)
            echo "Usage: $0 [--model MODEL] [--all] [--dry-run] [--skip-restart]"
            echo ""
            echo "Options:"
            echo "  --model MODEL   Deploy a specific model by name"
            echo "  --all           Deploy all available models"
            echo "  --dry-run       Show what would be done without executing"
            echo "  --skip-restart  Skip restarting the core service"
            exit 0 ;;
        *)
            if [[ "${shift_next:-}" == true ]]; then
                SPECIFIC_MODEL="$arg"
                shift_next=false
            else
                die "Unknown option: $arg"
            fi ;;
    esac
done

# ── Helpers ──
remote_kxkm() {
    if [[ "$DRY_RUN" == true ]]; then
        log "[dry-run] ssh ${KXKM_HOST} $*"
        return 0
    fi
    ssh -o ConnectTimeout=10 -o BatchMode=yes "${KXKM_HOST}" "$@"
}

remote_photon() {
    if [[ "$DRY_RUN" == true ]]; then
        log "[dry-run] ssh ${PHOTON_HOST} $*"
        return 0
    fi
    ssh -o ConnectTimeout=10 -o BatchMode=yes "${PHOTON_HOST}" "$@"
}

# ────────────────────────────────────────────────────────────
# Step 0: Connectivity
# ────────────────────────────────────────────────────────────
section "Connectivity check"

for host_label in "KXKM-AI:${KXKM_HOST}" "Photon:${PHOTON_HOST}"; do
    label="${host_label%%:*}"
    host="${host_label#*:}"
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" "echo ok" &>/dev/null; then
        ok "$label ($host)"
    else
        die "Cannot reach $label ($host)"
    fi
done

# ────────────────────────────────────────────────────────────
# Step 1: Determine which models to deploy
# ────────────────────────────────────────────────────────────
section "Selecting models to deploy"

declare -a DEPLOY_MODELS=()

if [[ -n "$SPECIFIC_MODEL" ]]; then
    DEPLOY_MODELS+=("$SPECIFIC_MODEL")
    log "Deploying specific model: ${SPECIFIC_MODEL}"

elif [[ "$DEPLOY_ALL" == true ]]; then
    # List all available models from KXKM-AI Ollama
    AVAILABLE=$(remote_kxkm "ollama list 2>/dev/null | tail -n +2 | awk '{print \$1}' | grep -i mascarade || true")
    if [[ -z "$AVAILABLE" ]]; then
        die "No mascarade models found in Ollama on KXKM-AI"
    fi
    while IFS= read -r m; do
        DEPLOY_MODELS+=("$m")
    done <<< "$AVAILABLE"
    log "Deploying all ${#DEPLOY_MODELS[@]} models"

else
    # Parse best models from benchmark report
    LOCAL_REPORT="${ROOT_DIR}/${REPORT_FILE}"
    if [[ ! -f "$LOCAL_REPORT" ]]; then
        # Try fetching from KXKM-AI
        REMOTE_REPORT=$(remote_kxkm "ls -t ${KXKM_DIR}/finetune/eval/benchmark-v4-*/BENCHMARK_V4_REPORT.md 2>/dev/null | head -1" || true)
        if [[ -n "$REMOTE_REPORT" ]]; then
            scp "${KXKM_HOST}:${REMOTE_REPORT}" "$LOCAL_REPORT" 2>/dev/null || true
        fi
    fi

    if [[ -f "$LOCAL_REPORT" ]]; then
        # Extract best overall model from report
        BEST=$(grep -oP 'Best overall model: `\K[^`]+' "$LOCAL_REPORT" 2>/dev/null || true)
        if [[ -n "$BEST" ]]; then
            DEPLOY_MODELS+=("$BEST")
            log "Best overall from report: ${BEST}"
        fi
        # Extract per-domain bests
        while IFS= read -r line; do
            model=$(echo "$line" | grep -oP '`\K[^`]+' 2>/dev/null || true)
            if [[ -n "$model" ]] && [[ ! " ${DEPLOY_MODELS[*]} " =~ " ${model} " ]]; then
                DEPLOY_MODELS+=("$model")
                log "Best for domain: ${model}"
            fi
        done < <(grep '^\- \*\*' "$LOCAL_REPORT" 2>/dev/null | grep '`' || true)
    fi

    if [[ ${#DEPLOY_MODELS[@]} -eq 0 ]]; then
        die "No models to deploy. Run benchmark-v4-all.sh first, or use --model or --all"
    fi
fi

ok "Will deploy ${#DEPLOY_MODELS[@]} model(s): ${DEPLOY_MODELS[*]}"

# ────────────────────────────────────────────────────────────
# Step 2: Copy models to photon
# ────────────────────────────────────────────────────────────
section "Copying models to photon"

# Ensure target directory exists
remote_photon "mkdir -p ${PHOTON_MODELS_DIR}"

for model in "${DEPLOY_MODELS[@]}"; do
    # Strip :latest tag if present
    model_clean="${model%%:latest}"
    model_clean="${model_clean%%:*}"

    log "Exporting ${model} from KXKM-AI Ollama..."

    if [[ "$DRY_RUN" == true ]]; then
        log "[dry-run] Would copy ${model} from KXKM-AI to photon"
        continue
    fi

    # Find the GGUF file from the benchmark import cache
    GGUF_PATH=$(remote_kxkm "ls /tmp/bench-v4-import/${model_clean}/model-*.gguf 2>/dev/null | head -1" || true)

    if [[ -z "$GGUF_PATH" ]]; then
        # Fallback: export from Ollama blob store
        log "  No cached GGUF, looking in Ollama blob store..."
        GGUF_PATH=$(remote_kxkm "ollama show '${model}' --modelfile 2>/dev/null | grep '^FROM ' | head -1 | awk '{print \$2}'" || true)
    fi

    if [[ -z "$GGUF_PATH" ]]; then
        warn "  Cannot find GGUF for ${model}, skipping"
        continue
    fi

    # Direct SCP from KXKM-AI to photon (via local pipe to avoid double storage)
    DEST="${PHOTON_MODELS_DIR}/${model_clean}.gguf"
    log "  Copying ${GGUF_PATH} -> photon:${DEST}"

    # Use ssh pipe to avoid storing on local machine
    ssh -o BatchMode=yes "${KXKM_HOST}" "cat '${GGUF_PATH}'" | \
        ssh -o BatchMode=yes "${PHOTON_HOST}" "cat > '${DEST}'"

    ok "  ${model_clean}.gguf copied to photon"

    # Also copy manifest if available
    MANIFEST_PATH=$(remote_kxkm "find ${KXKM_RUNS} -name manifest.json -path '*${model_clean}*' 2>/dev/null | head -1" || true)
    if [[ -n "$MANIFEST_PATH" ]]; then
        ssh -o BatchMode=yes "${KXKM_HOST}" "cat '${MANIFEST_PATH}'" | \
            ssh -o BatchMode=yes "${PHOTON_HOST}" "cat > '${PHOTON_MODELS_DIR}/${model_clean}_manifest.json'"
    fi
done

# ────────────────────────────────────────────────────────────
# Step 3: Configure ML router
# ────────────────────────────────────────────────────────────
section "Configuring ML router on photon"

if [[ "$DRY_RUN" == true ]]; then
    log "[dry-run] Would update ${PHOTON_CORE_CONFIG}"
else
    # Build router config with deployed models
    ROUTER_YAML="# ML Router configuration - auto-generated by deploy-to-photon.sh
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
#
# Models deployed from benchmark-v4 pipeline

models:"

    for model in "${DEPLOY_MODELS[@]}"; do
        model_clean="${model%%:latest}"
        model_clean="${model_clean%%:*}"
        ROUTER_YAML="${ROUTER_YAML}
  - name: \"${model_clean}\"
    path: \"${PHOTON_MODELS_DIR}/${model_clean}.gguf\"
    type: gguf
    backend: ollama
    enabled: true"
    done

    ROUTER_YAML="${ROUTER_YAML}

defaults:
  temperature: 0.3
  max_tokens: 2048
  timeout_s: 60

routing:
  strategy: domain-match
  fallback: mistral-small"

    # Backup existing config before overwriting
    remote_photon "if [ -f '${PHOTON_CORE_CONFIG}' ]; then cp '${PHOTON_CORE_CONFIG}' '${PHOTON_CORE_CONFIG}.bak.$(date +%s)'; fi"

    # Write new config
    remote_photon "mkdir -p $(dirname "${PHOTON_CORE_CONFIG}")"
    echo "$ROUTER_YAML" | ssh -o BatchMode=yes "${PHOTON_HOST}" "cat > '${PHOTON_CORE_CONFIG}'"

    ok "ML router config updated"
fi

# ────────────────────────────────────────────────────────────
# Step 4: Import models into Ollama on photon and restart core
# ────────────────────────────────────────────────────────────
if [[ "$SKIP_RESTART" == false ]]; then
    section "Importing models into photon Ollama"

    for model in "${DEPLOY_MODELS[@]}"; do
        model_clean="${model%%:latest}"
        model_clean="${model_clean%%:*}"

        if [[ "$DRY_RUN" == true ]]; then
            log "[dry-run] Would import ${model_clean} into photon Ollama"
            continue
        fi

        # Create Modelfile and import
        remote_photon bash -s <<OLLAMA_EOF
set -euo pipefail
GGUF="${PHOTON_MODELS_DIR}/${model_clean}.gguf"
if [[ ! -f "\${GGUF}" ]]; then
    echo "[skip] \${GGUF} not found"
    exit 0
fi

# Skip if already imported
if ollama show "${model_clean}" >/dev/null 2>&1; then
    echo "[ok] ${model_clean} already in Ollama"
    exit 0
fi

cat > "/tmp/Modelfile.${model_clean}" <<MF
FROM \${GGUF}
PARAMETER temperature 0.3
PARAMETER num_ctx 2048
SYSTEM "You are an expert electronics engineer specializing in PCB design, SPICE simulation, KiCad, and embedded systems."
MF

ollama create "${model_clean}" -f "/tmp/Modelfile.${model_clean}"
echo "[ok] ${model_clean} imported into Ollama"
OLLAMA_EOF
        ok "  ${model_clean} imported on photon"
    done

    section "Restarting mascarade core"

    if [[ "$DRY_RUN" == true ]]; then
        log "[dry-run] Would restart ${PHOTON_SERVICE}"
    else
        remote_photon "systemctl restart ${PHOTON_SERVICE} 2>/dev/null || docker compose -f ${PHOTON_DIR}/docker-compose.yml restart core 2>/dev/null || true"
        ok "Service restart triggered"

        # Wait for service to come up
        log "Waiting for core to be ready..."
        for i in $(seq 1 30); do
            if remote_photon "curl -sf http://localhost:8100/health >/dev/null 2>&1"; then
                ok "Core is healthy (attempt ${i})"
                break
            fi
            if [[ "$i" -eq 30 ]]; then
                warn "Core health check failed after 30s"
            fi
            sleep 1
        done
    fi
else
    log "Skipping restart (--skip-restart)"
fi

# ────────────────────────────────────────────────────────────
# Step 5: Health check
# ────────────────────────────────────────────────────────────
section "Health check"

if [[ "$DRY_RUN" == true ]]; then
    log "[dry-run] Would run health checks"
else
    # Check Ollama
    OLLAMA_OK=$(remote_photon "curl -sf http://localhost:${OLLAMA_PORT}/api/tags >/dev/null 2>&1 && echo yes || echo no")
    if [[ "$OLLAMA_OK" == "yes" ]]; then
        ok "Ollama is running on photon"
        # List deployed models
        remote_photon "ollama list 2>/dev/null | head -20" || true
    else
        warn "Ollama not responding on photon"
    fi

    # Check core health
    CORE_HEALTH=$(remote_photon "curl -sf http://localhost:8100/health 2>/dev/null" || echo '{"status":"unreachable"}')
    log "Core health: ${CORE_HEALTH}"

    # Quick inference test on each model
    for model in "${DEPLOY_MODELS[@]}"; do
        model_clean="${model%%:latest}"
        model_clean="${model_clean%%:*}"
        TEST_RESP=$(remote_photon "curl -sf http://localhost:${OLLAMA_PORT}/api/generate -d '{\"model\":\"${model_clean}\",\"prompt\":\"What is a bypass capacitor?\",\"stream\":false,\"options\":{\"num_predict\":50}}' 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"response\",\"ERROR\")[:80])' 2>/dev/null" || echo "ERROR")
        if [[ "$TEST_RESP" != "ERROR" ]] && [[ -n "$TEST_RESP" ]]; then
            ok "  ${model_clean}: responding"
        else
            warn "  ${model_clean}: not responding"
        fi
    done
fi

section "Deployment complete"
log "Models deployed: ${DEPLOY_MODELS[*]}"
log "Target: photon (${PHOTON_HOST})"
log "Config: ${PHOTON_CORE_CONFIG}"
