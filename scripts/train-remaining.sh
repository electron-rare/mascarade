#!/usr/bin/env bash
set -euo pipefail
cd /ai/saisail/mascarade
source .venv-finetune/bin/activate
export WANDB_DISABLED=true TOKENIZERS_PARALLELISM=false

# Models that failed — train one per process to avoid OOM accumulation
MODELS=(
    "mascarade-emc|finetune/datasets/emc_chat.jsonl|emc"
    "mascarade-analog|finetune/datasets/analog_audio_electronics_cleaned.jsonl|analog"
    "mascarade-power|finetune/datasets/power_chat.jsonl|power"
    "mascarade-dsp|finetune/datasets/dsp_chat.jsonl|dsp"
    "mascarade-embedded-v2|finetune/datasets/embedded_systems_full_cleaned.jsonl|embedded"
    "mascarade-missing|finetune/datasets/missing_domains_cleaned.jsonl|missing"
)

for entry in "${MODELS[@]}"; do
    IFS='|' read -r NAME DATASET DOMAIN <<< "$entry"
    
    # Skip if already done
    if ls finetune/runs/${NAME}-*/manifest.json 2>/dev/null | head -1 | grep -q manifest; then
        echo "SKIP $NAME (already trained)"
        continue
    fi
    
    if [ ! -f "$DATASET" ]; then
        echo "SKIP $NAME ($DATASET not found)"
        continue
    fi
    
    LINES=$(wc -l < "$DATASET")
    echo ""
    echo "============================================================"
    echo "TRAINING: $NAME ($LINES examples)"
    echo "============================================================"
    
    # Run in subprocess to isolate GPU memory
    python3 -u -c "
import json, time, os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['WANDB_DISABLED'] = 'true'
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

NAME='$NAME'; DS='$DATASET'; DOMAIN='$DOMAIN'
RUN=f'finetune/runs/{NAME}-{time.strftime(\"%Y%m%d-%H%M%S\")}'
os.makedirs(RUN, exist_ok=True)

m, t = FastLanguageModel.from_pretrained('unsloth/Qwen3-8B-unsloth-bnb-4bit', max_seq_length=1024, load_in_4bit=True)
m = FastLanguageModel.get_peft_model(m, r=16, lora_alpha=32, lora_dropout=0, bias='none', use_gradient_checkpointing='unsloth', target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'])

ds = load_dataset('json', data_files=DS, split='train')
def fmt(ex):
    txt = ''
    for c in ex.get('conversations', []):
        r = c.get('from', c.get('role', ''))
        v = c.get('value', c.get('content', ''))
        if not v: continue
        if r in ('system','human','user'): txt += f'<s>[INST] {v} [/INST]'
        elif r in ('assistant','gpt'): txt += f' {v}</s>'
    return {'text': txt}
ds = ds.map(fmt).filter(lambda x: len(x['text']) > 50)
n = len(ds); ep = 3 if n < 5000 else 2
print(f'{NAME}: {n} examples, {ep} epochs')

tr = SFTTrainer(model=m, args=SFTConfig(output_dir=RUN, num_train_epochs=ep, per_device_train_batch_size=2, gradient_accumulation_steps=8, learning_rate=2e-4, warmup_steps=min(50,n//16//10), logging_steps=25, save_steps=500, max_seq_length=1024, dataset_text_field='text', bf16=True, seed=42), train_dataset=ds, tokenizer=t)
s=time.time(); tr.train(); d=time.time()-s
print(f'DONE {d:.0f}s')
m.save_pretrained(f'{RUN}/lora'); t.save_pretrained(f'{RUN}/lora')
json.dump({'name':NAME,'dataset':DS,'domain':DOMAIN,'examples':n,'epochs':ep,'duration':d,'output':RUN}, open(f'{RUN}/manifest.json','w'), indent=2)
print(f'Saved: {RUN}')
" 2>&1
    
    echo "$NAME: exit code $?"
    # GPU memory is freed when subprocess exits
    sleep 5
done

echo ""
echo "============================================================"
echo "ALL REMAINING MODELS DONE"
echo "============================================================"
ls -d finetune/runs/mascarade-*/manifest.json 2>/dev/null | wc -l
