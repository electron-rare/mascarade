"""Auto-queue: train ALL mini-models sequentially."""
import json, time, os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["WANDB_DISABLED"] = "true"

BASE = "finetune/datasets"
RUNS = "finetune/runs"
BASE_MODEL = "unsloth/Qwen3-8B-unsloth-bnb-4bit"
SEQ = 1024; BATCH = 2; GA = 8; LR = 2e-4

QUEUE = [
    ("mascarade-ipc", f"{BASE}/ipc_jlcpcb_standards_cleaned.jsonl", "ipc"),
    ("mascarade-emc", f"{BASE}/emc_chat.jsonl", "emc"),
    ("mascarade-analog", f"{BASE}/analog_audio_electronics_cleaned.jsonl", "analog"),
    ("mascarade-power", f"{BASE}/power_chat.jsonl", "power"),
    ("mascarade-dsp", f"{BASE}/dsp_chat.jsonl", "dsp"),
    ("mascarade-kicad10", f"{BASE}/kicad10_features_cleaned.jsonl", "kicad10"),
    ("mascarade-embedded-v2", f"{BASE}/embedded_systems_full_cleaned.jsonl", "embedded"),
    ("mascarade-missing", f"{BASE}/missing_domains_cleaned.jsonl", "missing"),
    ("mascarade-kicad-v3", f"{BASE}/kicad_chat_v3_multi.jsonl", "kicad"),
]

def done(name):
    if not os.path.isdir(RUNS): return False
    return any(d.startswith(name) and os.path.isfile(f"{RUNS}/{d}/manifest.json") for d in os.listdir(RUNS))

def train(name, path, domain):
    from unsloth import FastLanguageModel
    from trl import SFTTrainer, SFTConfig
    from datasets import load_dataset
    n = sum(1 for _ in open(path))
    if n < 10: return None
    ep = 3 if n < 5000 else 2
    rd = f"{RUNS}/{name}-{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(rd, exist_ok=True)
    print(f"\n{'='*60}\nTRAINING: {name} ({n} ex, {ep} ep)\n{'='*60}")
    m, t = FastLanguageModel.from_pretrained(BASE_MODEL, max_seq_length=SEQ, load_in_4bit=True)
    m = FastLanguageModel.get_peft_model(m, r=16, lora_alpha=32, lora_dropout=0, bias="none", use_gradient_checkpointing="unsloth", target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
    ds = load_dataset("json", data_files=path, split="train")
    def fmt(ex):
        txt = ""
        for c in ex.get("conversations", []):
            rl = c.get("from", c.get("role", ""))
            vl = c.get("value", c.get("content", ""))
            if not vl: continue
            if rl in ("system","human","user"): txt += f"<s>[INST] {vl} [/INST]"
            elif rl in ("assistant","gpt"): txt += f" {vl}</s>"
        return {"text": txt}
    ds = ds.map(fmt).filter(lambda x: len(x["text"]) > 50)
    print(f"  Formatted: {len(ds)}")
    if len(ds) < 10: return None
    tr = SFTTrainer(model=m, args=SFTConfig(output_dir=rd, num_train_epochs=ep, per_device_train_batch_size=BATCH, gradient_accumulation_steps=GA, learning_rate=LR, warmup_steps=min(50, len(ds)//(BATCH*GA)//10), logging_steps=25, save_steps=500, max_seq_length=SEQ, dataset_text_field="text", bf16=True, seed=42), train_dataset=ds, tokenizer=t)
    s = time.time()
    tr.train()
    d = time.time() - s
    print(f"  DONE {d:.0f}s")
    m.save_pretrained(f"{rd}/lora"); t.save_pretrained(f"{rd}/lora")
    mf = {"name":name,"base":BASE_MODEL,"dataset":path,"domain":domain,"examples":len(ds),"epochs":ep,"duration":d,"output":rd,"ts":time.strftime("%Y-%m-%d %H:%M")}
    json.dump(mf, open(f"{rd}/manifest.json","w"), indent=2)
    del m, t, tr
    import torch; torch.cuda.empty_cache()
    import gc; gc.collect()
    return mf

results = []
for name, path, domain in QUEUE:
    if done(name): print(f"SKIP {name} (done)"); continue
    if not os.path.exists(path): print(f"SKIP {name} (no file)"); continue
    try:
        r = train(name, path, domain)
        if r: results.append(r)
    except Exception as e:
        print(f"FAILED {name}: {e}")
        import torch; torch.cuda.empty_cache()
        import gc; gc.collect()

print(f"\n{'='*60}\nDONE: {len(results)} models trained")
for r in results: print(f"  {r['name']}: {r['examples']} ex, {r['duration']:.0f}s")
json.dump({"trained":len(results),"results":results}, open(f"{RUNS}/queue_summary.json","w"), indent=2)
