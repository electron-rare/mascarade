#!/usr/bin/env bash
# T-MA-017: Fine-tune Codestral on SPICE + embedded dataset
# Target: KXKM-AI (RTX 4090, 24GB VRAM, Ubuntu, Python 3.12)
# Dataset: ~20k SPICE netlists, embedded C, PlatformIO examples
# Method: QLoRA 4-bit via Unsloth (preferred) or trl/peft fallback
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

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

# ── Config (all overridable via env) ──
BASE_MODEL="${BASE_MODEL:-mistralai/Codestral-2501}"
DATASET_PATH="${DATASET_PATH:-finetune/datasets/spice_embedded_dataset.jsonl}"
RUN_TAG="codestral-spice-$(date +%Y%m%d-%H%M%S)"
OUTPUT_DIR="${OUTPUT_DIR:-finetune/runs/${RUN_TAG}}"
LORA_R="${LORA_R:-16}"
LORA_ALPHA="${LORA_ALPHA:-32}"
LORA_DROPOUT="${LORA_DROPOUT:-0.05}"
# Codestral benefits from broader LoRA targets for code generation
TARGET_MODULES="${TARGET_MODULES:-q_proj,v_proj,k_proj,o_proj,gate_proj,up_proj,down_proj}"
EPOCHS="${EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-2}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"
LR="${LR:-1e-4}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-4096}"
QUANTIZATION="${QUANTIZATION:-4bit}"
WARMUP_RATIO="${WARMUP_RATIO:-0.05}"
WEIGHT_DECAY="${WEIGHT_DECAY:-0.01}"
BACKEND="${BACKEND:-auto}"
EXPORT_GGUF="${EXPORT_GGUF:-1}"
GGUF_QUANT="${GGUF_QUANT:-Q4_K_M}"
MANIFEST="${MANIFEST:-finetune/manifest.jsonl}"
DRY_RUN="${DRY_RUN:-0}"

# Code-specific: enable fill-in-middle (FIM) training if dataset supports it
FIM_ENABLED="${FIM_ENABLED:-1}"

# ── Banner ──
section "T-MA-017: Fine-tune Codestral on SPICE + Embedded"
log "base_model     = ${BASE_MODEL}"
log "dataset        = ${DATASET_PATH}"
log "output_dir     = ${OUTPUT_DIR}"
log "lora_r/alpha   = ${LORA_R}/${LORA_ALPHA}"
log "target_modules = ${TARGET_MODULES}"
log "epochs         = ${EPOCHS}"
log "batch_size     = ${BATCH_SIZE} (grad_accum=${GRAD_ACCUM})"
log "lr             = ${LR}"
log "max_seq_len    = ${MAX_SEQ_LEN}"
log "quantization   = ${QUANTIZATION}"
log "backend        = ${BACKEND}"
log "fim_enabled    = ${FIM_ENABLED}"
log "export_gguf    = ${EXPORT_GGUF} (${GGUF_QUANT})"

# ── Step 1: Check GPU ──
section "Step 1/6: GPU check"
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "unknown")
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0")
    GPU_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0")
    ok "GPU: ${GPU_NAME} (${GPU_MEM} MiB total, ${GPU_FREE} MiB free)"
    if [[ "${GPU_FREE}" -lt 20000 ]]; then
        warn "Less than 20GB VRAM free -- Codestral 22B QLoRA needs ~20GB"
    fi
else
    die "nvidia-smi not found -- this script requires an NVIDIA GPU"
fi

python3 -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'" 2>/dev/null \
    || die "PyTorch CUDA not available"

# ── Step 2: Validate dataset ──
section "Step 2/6: Dataset validation"
if [[ ! -f "${DATASET_PATH}" ]]; then
    die "Dataset not found: ${DATASET_PATH}"
fi

DATASET_LINES=$(wc -l < "${DATASET_PATH}" | tr -d ' ')
ok "Dataset: ${DATASET_PATH} (${DATASET_LINES} examples)"

if [[ "${DATASET_LINES}" -lt 100 ]]; then
    warn "Dataset has fewer than 100 examples -- results may be poor"
fi

# Validate JSONL + check for code-specific fields
log "Validating JSONL structure..."
python3 -c "
import json, sys
domains = {'spice': 0, 'embedded_c': 0, 'platformio': 0, 'other': 0}
with open('${DATASET_PATH}') as f:
    for i, line in enumerate(f):
        if i >= 20: break
        d = json.loads(line)
        assert 'messages' in d or 'instruction' in d or 'prompt' in d, \
            f'Line {i+1}: missing messages/instruction/prompt'
        # Count domain distribution
        text = json.dumps(d).lower()
        if '.subckt' in text or 'spice' in text or '.model' in text:
            domains['spice'] += 1
        elif 'platformio' in text or 'pio' in text:
            domains['platformio'] += 1
        elif '#include' in text or 'void ' in text or 'int main' in text:
            domains['embedded_c'] += 1
        else:
            domains['other'] += 1
print(f'Domain sample (first 20): {json.dumps(domains)}')
" || die "Invalid JSONL format in dataset"
ok "JSONL structure valid"

# ── Step 3: Prepare environment ──
section "Step 3/6: Environment setup"
mkdir -p "${OUTPUT_DIR}"

RESOLVED_BACKEND="${BACKEND}"
if [[ "${BACKEND}" == "auto" ]]; then
    if python3 -c "import unsloth" 2>/dev/null; then
        RESOLVED_BACKEND="unsloth"
        ok "Auto-selected Unsloth backend"
    else
        RESOLVED_BACKEND="trl"
        warn "Unsloth not found, falling back to trl/peft"
    fi
fi
log "Backend: ${RESOLVED_BACKEND}"

if [[ "${DRY_RUN}" == "1" ]]; then
    ok "DRY_RUN=1 -- would train with above config. Exiting."
    exit 0
fi

# ── Step 4: Run training ──
section "Step 4/6: Training"
TRAIN_START=$(date +%s)

if [[ "${RESOLVED_BACKEND}" == "unsloth" ]]; then
    log "Training via Unsloth (QLoRA ${QUANTIZATION})..."
    python3 -u - <<'TRAIN_SCRIPT'
import json, os, time
from pathlib import Path

base_model    = os.environ["BASE_MODEL"]
dataset_path  = os.environ["DATASET_PATH"]
output_dir    = os.environ["OUTPUT_DIR"]
lora_r        = int(os.environ.get("LORA_R", "16"))
lora_alpha    = int(os.environ.get("LORA_ALPHA", "32"))
lora_dropout  = float(os.environ.get("LORA_DROPOUT", "0.05"))
target_mods   = os.environ.get("TARGET_MODULES", "q_proj,v_proj,k_proj,o_proj").split(",")
epochs        = int(os.environ.get("EPOCHS", "3"))
batch_size    = int(os.environ.get("BATCH_SIZE", "2"))
grad_accum    = int(os.environ.get("GRAD_ACCUM", "8"))
lr            = float(os.environ.get("LR", "1e-4"))
max_seq_len   = int(os.environ.get("MAX_SEQ_LEN", "4096"))
warmup_ratio  = float(os.environ.get("WARMUP_RATIO", "0.05"))
weight_decay  = float(os.environ.get("WEIGHT_DECAY", "0.01"))
quantization  = os.environ.get("QUANTIZATION", "4bit")

print(f"[unsloth] Loading {base_model} ({quantization})...")
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=base_model,
    max_seq_length=max_seq_len,
    load_in_4bit=(quantization == "4bit"),
    dtype=None,
)

print(f"[unsloth] Applying LoRA (r={lora_r}, alpha={lora_alpha}, targets={target_mods})...")
model = FastLanguageModel.get_peft_model(
    model,
    r=lora_r,
    lora_alpha=lora_alpha,
    lora_dropout=lora_dropout,
    target_modules=target_mods,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

print(f"[unsloth] Loading dataset from {dataset_path}...")
from datasets import load_dataset
dataset = load_dataset("json", data_files=dataset_path, split="train")
print(f"[unsloth] Dataset: {len(dataset)} examples")

# Codestral chat template with code-aware formatting
def format_example(example):
    if "messages" in example:
        text = tokenizer.apply_chat_template(example["messages"], tokenize=False)
    elif "instruction" in example:
        messages = [
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example.get("output", example.get("response", ""))},
        ]
        if example.get("input"):
            messages[0]["content"] += "\n\n" + example["input"]
        text = tokenizer.apply_chat_template(messages, tokenize=False)
    else:
        text = example.get("text", example.get("prompt", ""))
    return {"text": text}

dataset = dataset.map(format_example, remove_columns=dataset.column_names)

from trl import SFTTrainer
from transformers import TrainingArguments

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_len,
    dataset_num_proc=4,
    packing=True,
    args=TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        num_train_epochs=epochs,
        learning_rate=lr,
        warmup_ratio=warmup_ratio,
        weight_decay=weight_decay,
        fp16=False,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        optim="adamw_8bit",
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",
    ),
)

print("[unsloth] Starting training...")
t0 = time.time()
stats = trainer.train()
elapsed = time.time() - t0

adapter_path = os.path.join(output_dir, "adapter")
model.save_pretrained(adapter_path)
tokenizer.save_pretrained(adapter_path)
print(f"[unsloth] Adapter saved to {adapter_path}")

result = {
    "base_model": base_model,
    "dataset": dataset_path,
    "method": "qlora-unsloth",
    "domain": "spice-embedded",
    "lora_r": lora_r,
    "lora_alpha": lora_alpha,
    "target_modules": target_mods,
    "epochs": epochs,
    "training_loss": stats.training_loss,
    "training_time_seconds": round(elapsed, 1),
    "adapter_path": adapter_path,
}
stats_path = os.path.join(output_dir, "training_stats.json")
with open(stats_path, "w") as f:
    json.dump(result, f, indent=2)
print(f"[unsloth] Stats: {json.dumps(result, indent=2)}")
TRAIN_SCRIPT

else
    log "Training via trl/peft (QLoRA ${QUANTIZATION})..."
    python3 -u - <<'TRAIN_SCRIPT_TRL'
import json, os, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer
from datasets import load_dataset

base_model    = os.environ["BASE_MODEL"]
dataset_path  = os.environ["DATASET_PATH"]
output_dir    = os.environ["OUTPUT_DIR"]
lora_r        = int(os.environ.get("LORA_R", "16"))
lora_alpha    = int(os.environ.get("LORA_ALPHA", "32"))
lora_dropout  = float(os.environ.get("LORA_DROPOUT", "0.05"))
target_mods   = os.environ.get("TARGET_MODULES", "q_proj,v_proj,k_proj,o_proj").split(",")
epochs        = int(os.environ.get("EPOCHS", "3"))
batch_size    = int(os.environ.get("BATCH_SIZE", "2"))
grad_accum    = int(os.environ.get("GRAD_ACCUM", "8"))
lr            = float(os.environ.get("LR", "1e-4"))
max_seq_len   = int(os.environ.get("MAX_SEQ_LEN", "4096"))
warmup_ratio  = float(os.environ.get("WARMUP_RATIO", "0.05"))
weight_decay  = float(os.environ.get("WEIGHT_DECAY", "0.01"))
quantization  = os.environ.get("QUANTIZATION", "4bit")

print(f"[trl] Loading {base_model} ({quantization})...")
bnb_config = None
if quantization == "4bit":
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
elif quantization == "8bit":
    bnb_config = BitsAndBytesConfig(load_in_8bit=True)

model = AutoModelForCausalLM.from_pretrained(
    base_model, quantization_config=bnb_config,
    device_map="auto", torch_dtype=torch.bfloat16, trust_remote_code=True,
)
tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = prepare_model_for_kbit_training(model)
peft_config = LoraConfig(
    r=lora_r, lora_alpha=lora_alpha, lora_dropout=lora_dropout,
    target_modules=target_mods, bias="none", task_type="CAUSAL_LM",
)
model = get_peft_model(model, peft_config)
model.print_trainable_parameters()

dataset = load_dataset("json", data_files=dataset_path, split="train")
print(f"[trl] Dataset: {len(dataset)} examples")

def format_example(example):
    if "messages" in example:
        text = tokenizer.apply_chat_template(example["messages"], tokenize=False)
    elif "instruction" in example:
        messages = [
            {"role": "user", "content": example["instruction"]},
            {"role": "assistant", "content": example.get("output", example.get("response", ""))},
        ]
        if example.get("input"):
            messages[0]["content"] += "\n\n" + example["input"]
        text = tokenizer.apply_chat_template(messages, tokenize=False)
    else:
        text = example.get("text", example.get("prompt", ""))
    return {"text": text}

dataset = dataset.map(format_example, remove_columns=dataset.column_names)

trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=dataset,
    dataset_text_field="text", max_seq_length=max_seq_len, packing=True,
    args=TrainingArguments(
        output_dir=output_dir, per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum, num_train_epochs=epochs,
        learning_rate=lr, warmup_ratio=warmup_ratio, weight_decay=weight_decay,
        fp16=False, bf16=True, logging_steps=10, save_strategy="epoch",
        save_total_limit=2, optim="adamw_8bit", lr_scheduler_type="cosine",
        seed=42, report_to="none",
    ),
)

print("[trl] Starting training...")
t0 = time.time()
stats = trainer.train()
elapsed = time.time() - t0

adapter_path = os.path.join(output_dir, "adapter")
model.save_pretrained(adapter_path)
tokenizer.save_pretrained(adapter_path)

result = {
    "base_model": base_model, "dataset": dataset_path,
    "method": "qlora-trl", "domain": "spice-embedded",
    "lora_r": lora_r, "lora_alpha": lora_alpha,
    "epochs": epochs, "training_loss": stats.training_loss,
    "training_time_seconds": round(elapsed, 1), "adapter_path": adapter_path,
}
with open(os.path.join(output_dir, "training_stats.json"), "w") as f:
    json.dump(result, f, indent=2)
print(f"[trl] Stats: {json.dumps(result, indent=2)}")
TRAIN_SCRIPT_TRL
fi

TRAIN_END=$(date +%s)
TRAIN_ELAPSED=$((TRAIN_END - TRAIN_START))
ok "Training completed in ${TRAIN_ELAPSED}s"

# ── Step 5: Merge LoRA and export GGUF ──
if [[ "${EXPORT_GGUF}" == "1" ]]; then
    section "Step 5/6: Merge LoRA + Export GGUF"
    log "Merging adapter into base model..."

    python3 -u - <<'MERGE_SCRIPT'
import os

output_dir   = os.environ["OUTPUT_DIR"]
base_model   = os.environ["BASE_MODEL"]
gguf_quant   = os.environ.get("GGUF_QUANT", "Q4_K_M")
adapter_path = os.path.join(output_dir, "adapter")
merged_path  = os.path.join(output_dir, "merged")

try:
    from unsloth import FastLanguageModel
    print("[merge] Loading model + adapter via Unsloth...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_path,
        max_seq_length=int(os.environ.get("MAX_SEQ_LEN", "4096")),
        load_in_4bit=True,
    )
    print(f"[merge] Saving merged model to {merged_path}...")
    model.save_pretrained_merged(merged_path, tokenizer, save_method="merged_16bit")

    print(f"[merge] Exporting GGUF ({gguf_quant})...")
    model.save_pretrained_gguf(output_dir, tokenizer, quantization_method=gguf_quant)
    print("[merge] GGUF exported")

except ImportError:
    print("[merge] Unsloth not available, using peft merge...")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.float16, device_map="cpu", trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base, adapter_path)
    model = model.merge_and_unload()
    os.makedirs(merged_path, exist_ok=True)
    model.save_pretrained(merged_path)
    tokenizer.save_pretrained(merged_path)
    print(f"[merge] Merged to {merged_path}. For GGUF, use llama.cpp convert.")
MERGE_SCRIPT

    ok "Merge + GGUF export complete"
else
    section "Step 5/6: GGUF export skipped (EXPORT_GGUF=0)"
fi

# ── Step 6: Log results to manifest ──
section "Step 6/6: Log to manifest"
mkdir -p "$(dirname "${MANIFEST}")"

MANIFEST_ENTRY=$(python3 -c "
import json, os
entry = {
    'task': 'T-MA-017',
    'run_tag': '${RUN_TAG}',
    'base_model': '${BASE_MODEL}',
    'dataset': '${DATASET_PATH}',
    'domain': 'spice-embedded',
    'output_dir': '${OUTPUT_DIR}',
    'config': {
        'lora_r': ${LORA_R}, 'lora_alpha': ${LORA_ALPHA},
        'target_modules': '${TARGET_MODULES}',
        'epochs': ${EPOCHS}, 'batch_size': ${BATCH_SIZE},
        'lr': '${LR}', 'quantization': '${QUANTIZATION}',
        'max_seq_len': ${MAX_SEQ_LEN},
    },
    'training_time_seconds': ${TRAIN_ELAPSED},
    'status': 'complete',
}
stats_path = os.path.join('${OUTPUT_DIR}', 'training_stats.json')
if os.path.exists(stats_path):
    with open(stats_path) as f:
        entry['training_stats'] = json.load(f)
print(json.dumps(entry))
")

echo "${MANIFEST_ENTRY}" >> "${MANIFEST}"
ok "Logged to ${MANIFEST}"

ln -sfn "$(basename "${OUTPUT_DIR}")" "$(dirname "${OUTPUT_DIR}")/codestral-spice-latest"
ok "Symlinked codestral-spice-latest -> ${RUN_TAG}"

echo ""
ok "T-MA-017 complete: ${OUTPUT_DIR}"
log "Adapter:  ${OUTPUT_DIR}/adapter/"
log "Merged:   ${OUTPUT_DIR}/merged/"
if [[ "${EXPORT_GGUF}" == "1" ]]; then
    log "GGUF:     ${OUTPUT_DIR}/model-${GGUF_QUANT}.gguf"
fi
log "Stats:    ${OUTPUT_DIR}/training_stats.json"
log "Manifest: ${MANIFEST}"
