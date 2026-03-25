#!/usr/bin/env bash
set -euo pipefail
cd /ai/saisail/mascarade
source .venv-finetune/bin/activate
export WANDB_DISABLED=true TOKENIZERS_PARALLELISM=false

CLEAN="finetune/datasets/cleaned_final"

MODELS=(
    "mascarade-spice-v3|${CLEAN}/spice_final.jsonl|spice"
    "mascarade-dsp-v2|${CLEAN}/dsp_final.jsonl|dsp"
    "mascarade-ipc-v2|${CLEAN}/ipc_final.jsonl|ipc"
    "mascarade-power-v2|${CLEAN}/power_final.jsonl|power"
    "mascarade-emc-v2|${CLEAN}/emc_final.jsonl|emc"
    "mascarade-embedded-v3|${CLEAN}/embedded_final.jsonl|embedded"
    "mascarade-iot-v2|${CLEAN}/iot_final.jsonl|iot"
    "mascarade-analog-v2|${CLEAN}/analog_final.jsonl|analog"
    "mascarade-freecad-v1|${CLEAN}/freecad_final.jsonl|freecad"
    "mascarade-kicad-v4|${CLEAN}/kicad-v3_final.jsonl|kicad"
    "mascarade-platformio-v1|${CLEAN}/platformio_final.jsonl|platformio"
    "mascarade-verilog-v1|${CLEAN}/rtlcoder3_final.jsonl|verilog"
    "mascarade-missing-v2|${CLEAN}/missing_final.jsonl|missing"
    "mascarade-stm32-v1|${CLEAN}/stm32_final.jsonl|stm32"
)

DONE=0
FAILED=0
for entry in "${MODELS[@]}"; do
    IFS='|' read -r NAME DATASET DOMAIN <<< "$entry"
    
    [ ! -f "$DATASET" ] && echo "SKIP $NAME (no file)" && continue
    LINES=$(wc -l < "$DATASET")
    [ "$LINES" -lt 50 ] && echo "SKIP $NAME ($LINES lines too few)" && continue
    
    echo ""
    echo "============================================================"
    echo "TRAINING: $NAME ($LINES examples)"
    echo "============================================================"
    
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
n = len(ds)
if n < 10:
    print(f'SKIP {NAME}: {n} examples after format')
    exit(0)
ep = 3 if n < 5000 else 2
print(f'{NAME}: {n} formatted, {ep} epochs')

tr = SFTTrainer(model=m, args=SFTConfig(output_dir=RUN, num_train_epochs=ep, per_device_train_batch_size=2, gradient_accumulation_steps=8, learning_rate=2e-4, warmup_steps=min(50,n//16//10), logging_steps=25, save_steps=500, max_seq_length=1024, dataset_text_field='text', bf16=True, seed=42), train_dataset=ds, tokenizer=t)
s=time.time(); tr.train(); d=time.time()-s
print(f'DONE {d:.0f}s')
m.save_pretrained(f'{RUN}/lora'); t.save_pretrained(f'{RUN}/lora')
json.dump({'name':NAME,'dataset':DS,'domain':DOMAIN,'examples':n,'epochs':ep,'duration':d,'output':RUN,'data_version':'enriched_v2'}, open(f'{RUN}/manifest.json','w'), indent=2)
" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "$NAME: OK"
        DONE=$((DONE+1))
    else
        echo "$NAME: FAILED"
        FAILED=$((FAILED+1))
    fi
    sleep 5
done

echo ""
echo "============================================================"
echo "DONE: $DONE trained, $FAILED failed"
echo "============================================================"
