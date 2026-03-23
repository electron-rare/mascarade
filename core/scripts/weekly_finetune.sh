#!/usr/bin/env bash
# Weekly fine-tune script — runs on GrosMac, triggers training on KXKM-AI via SSH
# Cron: 0 3 * * 0 /Users/electron/Documents/Projets/mascarade/core/scripts/weekly_finetune.sh
set -euo pipefail

LOG="/tmp/weekly-finetune-$(date +%Y%m%d).log"
KXKM="kxkm@kxkm-ai"
VENV="/home/kxkm/venv"
WORKDIR="/home/kxkm/mascarade/core"
RUN_NAME="weekly-$(date +%Y%m%d)"

echo "$(date): Starting weekly fine-tune run: $RUN_NAME" | tee "$LOG"

# Step 1: Train LoRA on KXKM-AI GPU
echo "$(date): Step 1 — Training LoRA on KXKM-AI..." | tee -a "$LOG"
ssh -o StrictHostKeyChecking=no "$KXKM" "
source $VENV/bin/activate
cd $WORKDIR
PYTHONPATH=. python3 -c \"
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig
import time

start = time.time()
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name='Qwen/Qwen2.5-Coder-1.5B-Instruct',
    max_seq_length=2048, dtype=None, load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=32,
    target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'],
    lora_dropout=0, bias='none', use_gradient_checkpointing='unsloth',
)
ds = load_dataset('ise-uiuc/Magicoder-OSS-Instruct-75K', split='train[:5000]')
ds = ds.map(lambda ex: {'text': ex['problem'][:1024]})

trainer = SFTTrainer(
    model=model, processing_class=tokenizer, train_dataset=ds,
    args=SFTConfig(
        output_dir='/tmp/ft-$RUN_NAME',
        per_device_train_batch_size=4, gradient_accumulation_steps=2,
        num_train_epochs=1, logging_steps=50, learning_rate=2e-4,
        fp16=False, bf16=True, dataset_text_field='text',
    ),
)
trainer.train()
loss = trainer.state.log_history[-1].get('train_loss', 'N/A')
print(f'Training done in {time.time()-start:.0f}s, loss: {loss}')
model.save_pretrained('/tmp/ft-$RUN_NAME/adapter')
tokenizer.save_pretrained('/tmp/ft-$RUN_NAME/adapter')
\"
" 2>&1 | tee -a "$LOG"

# Step 2: Merge LoRA
echo "$(date): Step 2 — Merging adapter..." | tee -a "$LOG"
ssh -o StrictHostKeyChecking=no "$KXKM" "
source $VENV/bin/activate
python3 -c \"
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-Coder-1.5B-Instruct', dtype=torch.bfloat16, device_map='cpu')
tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-Coder-1.5B-Instruct')
model = PeftModel.from_pretrained(base, '/tmp/ft-$RUN_NAME/adapter')
model = model.merge_and_unload()
model.save_pretrained('/tmp/ft-$RUN_NAME/merged')
tokenizer.save_pretrained('/tmp/ft-$RUN_NAME/merged')
print('Merge done')
\"
" 2>&1 | tee -a "$LOG"

# Step 3: Convert to GGUF Q4_K_M
echo "$(date): Step 3 — GGUF conversion..." | tee -a "$LOG"
ssh -o StrictHostKeyChecking=no "$KXKM" "
source $VENV/bin/activate
python3 ~/llama.cpp/convert_hf_to_gguf.py /tmp/ft-$RUN_NAME/merged --outfile /tmp/ft-$RUN_NAME/model-f16.gguf --outtype f16
~/llama.cpp/build/bin/llama-quantize /tmp/ft-$RUN_NAME/model-f16.gguf /tmp/ft-$RUN_NAME/model-q4km.gguf Q4_K_M
" 2>&1 | tee -a "$LOG"

# Step 4: Register in Ollama
echo "$(date): Step 4 — Ollama registration..." | tee -a "$LOG"
ssh -o StrictHostKeyChecking=no "$KXKM" "
cat > /tmp/ft-$RUN_NAME/Modelfile << 'MEOF'
FROM /tmp/ft-$RUN_NAME/model-q4km.gguf
TEMPLATE \"{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>\"
PARAMETER stop \"<|im_end|>\"
PARAMETER temperature 0.2
SYSTEM \"You are a helpful coding assistant.\"
MEOF
ollama create mascarade-coder-$RUN_NAME -f /tmp/ft-$RUN_NAME/Modelfile
ollama create mascarade-coder-latest -f /tmp/ft-$RUN_NAME/Modelfile
" 2>&1 | tee -a "$LOG"

echo "$(date): Weekly fine-tune complete: $RUN_NAME" | tee -a "$LOG"
