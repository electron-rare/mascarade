#!/usr/bin/env bash
# publish-hf.sh — Publish LoRA adapters and datasets to HuggingFace
# Uploads all LoRA adapters under clemsail/ namespace with auto-generated model cards.
# Also uploads curated datasets.
#
# Usage: ./scripts/publish-hf.sh [--dry-run] [--skip-datasets] [--skip-models] [--local]
#
# By default fetches from KXKM-AI. Use --local if runs are already synced locally.
#
# Requires:
#   - huggingface-cli or huggingface_hub Python package
#   - HF_TOKEN environment variable or token in script
#   - SSH access to kxkm@100.87.54.119 (unless --local)

set -euo pipefail

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────
HF_NAMESPACE="${HF_NAMESPACE:-clemsail}"
HF_TOKEN="${HF_TOKEN:-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}"

KXKM_HOST="${KXKM_HOST:-kxkm@100.87.54.119}"
REMOTE_RUNS="/ai/saisail/mascarade/finetune/runs"
REMOTE_DATASETS="/ai/saisail/mascarade/finetune/datasets/cleaned_final"

LOCAL_STAGING="/tmp/hf-publish-staging"

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
SKIP_DATASETS=false
SKIP_MODELS=false
USE_LOCAL=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)        DRY_RUN=true ;;
        --skip-datasets)  SKIP_DATASETS=true ;;
        --skip-models)    SKIP_MODELS=true ;;
        --local)          USE_LOCAL=true ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--skip-datasets] [--skip-models] [--local]"
            echo ""
            echo "Options:"
            echo "  --dry-run        Show what would be done without uploading"
            echo "  --skip-datasets  Skip dataset upload"
            echo "  --skip-models    Skip model/LoRA upload"
            echo "  --local          Use local finetune/runs instead of fetching from KXKM-AI"
            exit 0 ;;
        *)  die "Unknown option: $arg" ;;
    esac
done

# ── Helpers ──
remote() {
    ssh -o ConnectTimeout=10 -o BatchMode=yes "${KXKM_HOST}" "$@"
}

ensure_hf_cli() {
    if command -v huggingface-cli &>/dev/null; then
        return 0
    fi
    if python3 -c "from huggingface_hub import HfApi" &>/dev/null; then
        return 0
    fi
    die "huggingface-cli or huggingface_hub not found. Install with: pip install huggingface_hub"
}

hf_login() {
    export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
    export HF_TOKEN="$HF_TOKEN"
    if command -v huggingface-cli &>/dev/null; then
        echo "$HF_TOKEN" | huggingface-cli login --token "$HF_TOKEN" 2>/dev/null || true
    fi
}

# ────────────────────────────────────────────────────────────
# Step 0: Prerequisites
# ────────────────────────────────────────────────────────────
section "Prerequisites"

ensure_hf_cli
ok "HuggingFace CLI available"

if [[ "$USE_LOCAL" == false ]]; then
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${KXKM_HOST}" "echo ok" &>/dev/null; then
        die "Cannot SSH to ${KXKM_HOST}"
    fi
    ok "SSH to KXKM-AI"
fi

hf_login
ok "HuggingFace authenticated as ${HF_NAMESPACE}"

mkdir -p "$LOCAL_STAGING"

# ────────────────────────────────────────────────────────────
# Step 1: Upload LoRA adapters
# ────────────────────────────────────────────────────────────
if [[ "$SKIP_MODELS" == false ]]; then
    section "Discovering LoRA runs"

    if [[ "$USE_LOCAL" == true ]]; then
        LOCAL_RUNS="${ROOT_DIR}/finetune/runs"
        MANIFESTS=$(find "$LOCAL_RUNS" -maxdepth 2 -name manifest.json -path "*/mascarade-*/manifest.json" 2>/dev/null | sort || true)
    else
        # Fetch manifest list from remote
        MANIFESTS_REMOTE=$(remote "find ${REMOTE_RUNS} -maxdepth 2 -name manifest.json -path '*/mascarade-*/manifest.json' 2>/dev/null | sort" || true)
        if [[ -z "$MANIFESTS_REMOTE" ]]; then
            warn "No training runs found on KXKM-AI"
            MANIFESTS=""
        else
            # Sync runs locally for upload
            MANIFESTS=""
            while IFS= read -r remote_manifest; do
                run_dir=$(dirname "$remote_manifest")
                run_name=$(basename "$run_dir")
                local_run="${LOCAL_STAGING}/runs/${run_name}"

                if [[ -d "${local_run}/lora" ]]; then
                    log "  ${run_name}: already staged"
                else
                    log "  Fetching ${run_name}..."
                    mkdir -p "$local_run"
                    # Copy manifest + lora directory (skip large merged models)
                    scp -q "${KXKM_HOST}:${remote_manifest}" "${local_run}/manifest.json"
                    rsync -az --info=progress2 \
                        "${KXKM_HOST}:${run_dir}/lora/" "${local_run}/lora/" 2>/dev/null || \
                        scp -rq "${KXKM_HOST}:${run_dir}/lora" "${local_run}/" 2>/dev/null || true
                    # Copy training logs if available
                    scp -q "${KXKM_HOST}:${run_dir}/training_log.json" "${local_run}/" 2>/dev/null || true
                fi

                MANIFESTS="${MANIFESTS}${local_run}/manifest.json
"
            done <<< "$MANIFESTS_REMOTE"
        fi
    fi

    if [[ -z "$MANIFESTS" ]]; then
        warn "No LoRA runs to upload"
    else
        section "Uploading LoRA adapters to HuggingFace"

        while IFS= read -r manifest_path; do
            [[ -z "$manifest_path" ]] && continue
            run_dir=$(dirname "$manifest_path")
            lora_dir="${run_dir}/lora"

            if [[ ! -d "$lora_dir" ]]; then
                warn "  No lora/ in ${run_dir}, skipping"
                continue
            fi

            # Read manifest
            run_name=$(basename "$run_dir")

            # Generate repo name and model card via Python
            python3 - "$manifest_path" "$run_dir" "$HF_NAMESPACE" "$HF_TOKEN" "$DRY_RUN" <<'PYEOF'
import json
import sys
import os

manifest_path, run_dir, namespace, hf_token, dry_run_str = sys.argv[1:6]
dry_run = dry_run_str == "true"
lora_dir = os.path.join(run_dir, "lora")

with open(manifest_path) as f:
    manifest = json.load(f)

# Build repo name
name = manifest.get("name", os.path.basename(run_dir))
# Clean for HF repo name
repo_name = name.lower().replace(" ", "-").replace("_", "-")
if not repo_name.startswith("mascarade-"):
    repo_name = f"mascarade-{repo_name}"
repo_id = f"{namespace}/{repo_name}"

# Build model card
base_model = manifest.get("base_model", "unknown")
domain = manifest.get("domain", manifest.get("task", "general"))
epochs = manifest.get("epochs", manifest.get("num_train_epochs", "?"))
lr = manifest.get("learning_rate", manifest.get("lr", "?"))
dataset = manifest.get("dataset", manifest.get("train_dataset", "?"))
lora_rank = manifest.get("lora_rank", manifest.get("lora_r", "?"))
lora_alpha = manifest.get("lora_alpha", "?")
train_loss = manifest.get("final_loss", manifest.get("train_loss", "?"))
eval_loss = manifest.get("eval_loss", "?")
date = manifest.get("date", manifest.get("timestamp", "?"))

model_card = f"""---
language:
  - en
  - fr
license: apache-2.0
library_name: peft
base_model: {base_model}
tags:
  - mascarade
  - electronics
  - {domain}
  - lora
  - fine-tuned
---

# {name}

LoRA adapter fine-tuned for the [Mascarade](https://github.com/electron-rare/mascarade) multi-agent system.

## Model Details

| Parameter | Value |
|-----------|-------|
| Base model | `{base_model}` |
| Domain | {domain} |
| LoRA rank | {lora_rank} |
| LoRA alpha | {lora_alpha} |
| Epochs | {epochs} |
| Learning rate | {lr} |
| Train loss | {train_loss} |
| Eval loss | {eval_loss} |
| Date | {date} |

## Training Dataset

{dataset}

## Usage

```python
from peft import PeftModel, PeftConfig
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("{base_model}")
model = PeftModel.from_pretrained(base, "{repo_id}")
tokenizer = AutoTokenizer.from_pretrained("{base_model}")
```

## Part of Mascarade

This adapter is part of the Mascarade project - a multi-agent system for electronics engineering
(PCB design, SPICE simulation, KiCad, embedded systems).

## License

Apache 2.0
"""

# Write model card to lora directory
readme_path = os.path.join(lora_dir, "README.md")
with open(readme_path, "w") as f:
    f.write(model_card)

print(f"  Model card written for {repo_id}")

if dry_run:
    print(f"  [dry-run] Would upload {lora_dir} -> {repo_id}")
else:
    from huggingface_hub import HfApi
    api = HfApi(token=hf_token)

    # Create repo if it doesn't exist (idempotent)
    api.create_repo(repo_id=repo_id, repo_type="model", exist_ok=True, private=False)

    # Upload the lora directory
    api.upload_folder(
        repo_id=repo_id,
        folder_path=lora_dir,
        repo_type="model",
        commit_message=f"Upload LoRA adapter: {name}",
    )

    # Also upload manifest
    if os.path.isfile(manifest_path):
        api.upload_file(
            repo_id=repo_id,
            path_or_fileobj=manifest_path,
            path_in_repo="manifest.json",
            repo_type="model",
            commit_message="Add training manifest",
        )

    # Upload training log if available
    training_log = os.path.join(run_dir, "training_log.json")
    if os.path.isfile(training_log):
        api.upload_file(
            repo_id=repo_id,
            path_or_fileobj=training_log,
            path_in_repo="training_log.json",
            repo_type="model",
            commit_message="Add training log",
        )

    print(f"  [ok] Uploaded to https://huggingface.co/{repo_id}")
PYEOF

            if [[ $? -eq 0 ]]; then
                ok "  ${run_name} published"
            else
                warn "  ${run_name} upload failed"
            fi
        done <<< "$MANIFESTS"
    fi
else
    log "Skipping model upload (--skip-models)"
fi

# ────────────────────────────────────────────────────────────
# Step 2: Upload curated datasets
# ────────────────────────────────────────────────────────────
if [[ "$SKIP_DATASETS" == false ]]; then
    section "Uploading curated datasets"

    DATASETS_LOCAL="${LOCAL_STAGING}/datasets"
    mkdir -p "$DATASETS_LOCAL"

    if [[ "$USE_LOCAL" == true ]]; then
        DATASETS_SRC="${ROOT_DIR}/finetune/datasets/cleaned_final"
    else
        # Sync datasets from KXKM-AI
        DATASETS_SRC="${DATASETS_LOCAL}"
        REMOTE_DATASETS_LIST=$(remote "ls ${REMOTE_DATASETS}/*.jsonl 2>/dev/null || ls ${REMOTE_DATASETS}/*.json 2>/dev/null || echo ''" || true)

        if [[ -z "$REMOTE_DATASETS_LIST" ]]; then
            warn "No datasets found at ${REMOTE_DATASETS} on KXKM-AI"
            DATASETS_SRC=""
        else
            log "Syncing datasets from KXKM-AI..."
            rsync -az --info=progress2 \
                "${KXKM_HOST}:${REMOTE_DATASETS}/" "${DATASETS_LOCAL}/" 2>/dev/null || \
                scp -rq "${KXKM_HOST}:${REMOTE_DATASETS}/"* "${DATASETS_LOCAL}/" 2>/dev/null || true
            ok "Datasets synced"
        fi
    fi

    if [[ -n "${DATASETS_SRC:-}" ]] && [[ -d "$DATASETS_SRC" ]]; then
        # Find all dataset files
        DATASET_FILES=$(find "$DATASETS_SRC" -maxdepth 1 \( -name "*.jsonl" -o -name "*.json" -o -name "*.parquet" \) 2>/dev/null | sort || true)

        if [[ -z "$DATASET_FILES" ]]; then
            warn "No dataset files found in ${DATASETS_SRC}"
        else
            DATASET_COUNT=$(echo "$DATASET_FILES" | wc -l | tr -d ' ')
            log "Found ${DATASET_COUNT} dataset file(s)"

            python3 - "$DATASETS_SRC" "$HF_NAMESPACE" "$HF_TOKEN" "$DRY_RUN" <<'PYEOF'
import sys
import os
import json
import glob

datasets_dir, namespace, hf_token, dry_run_str = sys.argv[1:5]
dry_run = dry_run_str == "true"

REPO_ID = f"{namespace}/mascarade-datasets"

# Collect all dataset files
files = sorted(
    glob.glob(os.path.join(datasets_dir, "*.jsonl")) +
    glob.glob(os.path.join(datasets_dir, "*.json")) +
    glob.glob(os.path.join(datasets_dir, "*.parquet"))
)

if not files:
    print("  No dataset files found")
    sys.exit(0)

# Build dataset card
domains = set()
total_samples = 0
file_info = []
for fpath in files:
    fname = os.path.basename(fpath)
    # Try to count samples
    count = 0
    if fpath.endswith(".jsonl"):
        with open(fpath) as f:
            count = sum(1 for line in f if line.strip())
    elif fpath.endswith(".json"):
        try:
            with open(fpath) as f:
                data = json.load(f)
                count = len(data) if isinstance(data, list) else 1
        except Exception:
            pass

    total_samples += count
    # Infer domain from filename
    for d in ["kicad", "spice", "embedded", "pcb", "stm32", "platformio", "analog", "ipc", "audio"]:
        if d in fname.lower():
            domains.add(d)

    file_info.append({"name": fname, "samples": count})

dataset_card = f"""---
language:
  - en
  - fr
license: apache-2.0
tags:
  - mascarade
  - electronics
  - fine-tuning
  - curated
size_categories:
  - 1K<n<10K
---

# Mascarade Curated Datasets

Curated training datasets for the [Mascarade](https://github.com/electron-rare/mascarade) multi-agent system.

## Overview

| Metric | Value |
|--------|-------|
| Total files | {len(files)} |
| Total samples | {total_samples} |
| Domains | {', '.join(sorted(domains)) if domains else 'general'} |
| Format | JSONL / JSON |

## Files

| File | Samples |
|------|---------|
""" + "\n".join(f"| `{fi['name']}` | {fi['samples']} |" for fi in file_info) + """

## Usage

```python
from datasets import load_dataset
ds = load_dataset("{repo_id}")
```

## License

Apache 2.0
""".replace("{repo_id}", REPO_ID)

# Write README
readme_path = os.path.join(datasets_dir, "README.md")
with open(readme_path, "w") as f:
    f.write(dataset_card)

print(f"  Dataset card written ({len(files)} files, {total_samples} samples)")

if dry_run:
    print(f"  [dry-run] Would upload {len(files)} files to {REPO_ID}")
    for fi in file_info:
        print(f"    - {fi['name']} ({fi['samples']} samples)")
else:
    from huggingface_hub import HfApi
    api = HfApi(token=hf_token)

    # Create dataset repo (idempotent)
    api.create_repo(repo_id=REPO_ID, repo_type="dataset", exist_ok=True, private=False)

    # Upload entire directory
    api.upload_folder(
        repo_id=REPO_ID,
        folder_path=datasets_dir,
        repo_type="dataset",
        commit_message=f"Upload curated datasets ({len(files)} files, {total_samples} samples)",
    )

    print(f"  [ok] Uploaded to https://huggingface.co/datasets/{REPO_ID}")
PYEOF

            if [[ $? -eq 0 ]]; then
                ok "Datasets published"
            else
                warn "Dataset upload had errors"
            fi
        fi
    else
        warn "No datasets directory available"
    fi
else
    log "Skipping dataset upload (--skip-datasets)"
fi

# ────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────
section "Done"
log "Namespace: https://huggingface.co/${HF_NAMESPACE}"
if [[ "$SKIP_MODELS" == false ]]; then
    log "Models published under ${HF_NAMESPACE}/mascarade-*"
fi
if [[ "$SKIP_DATASETS" == false ]]; then
    log "Datasets: https://huggingface.co/datasets/${HF_NAMESPACE}/mascarade-datasets"
fi
if [[ "$DRY_RUN" == true ]]; then
    warn "This was a dry run. No uploads were made."
fi
