"""Continued Pre-Training (CPT) on 378K+ raw code.

Stage 1 of 3: CPT -> SFT -> RLVR
This teaches the model Verilog/KiCad/SPICE syntax by exposure to real code.
Uses causal LM objective (next token prediction), NOT instruction tuning."""

import json
import time
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["WANDB_DISABLED"] = "true"

DATASET = "finetune/datasets/cpt_code_378k.jsonl"
RUNS = "finetune/runs"
BASE_MODEL = "unsloth/Qwen3-8B-unsloth-bnb-4bit"
SEQ = 1024
SAMPLE = 50000  # Start with 50K, can increase later

print("=== Continued Pre-Training (CPT) ===")
print(f"Dataset: {DATASET}")
print(f"Sample: {SAMPLE}")

from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

RUN = f"{RUNS}/cpt-code-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(RUN, exist_ok=True)

model, tokenizer = FastLanguageModel.from_pretrained(
    BASE_MODEL,
    max_seq_length=SEQ,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r=32,
    lora_alpha=64,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
)

ds = load_dataset("json", data_files=DATASET, split="train")
print(f"Full: {len(ds)} examples")

if len(ds) > SAMPLE:
    ds = ds.shuffle(seed=42).select(range(SAMPLE))
    print(f"Sampled: {SAMPLE}")

ds = ds.filter(lambda x: x.get("text") and len(x["text"]) > 50)
print(f"Filtered: {len(ds)}")

# CPT: just raw text, no instruction formatting
# The model learns syntax by predicting next tokens
trainer = SFTTrainer(
    model=model,
    args=SFTConfig(
        output_dir=RUN,
        num_train_epochs=1,  # 1 epoch on 50K is enough for CPT
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=5e-5,  # Lower LR for CPT (don't destroy base knowledge)
        warmup_steps=100,
        logging_steps=50,
        save_steps=1000,
        max_seq_length=SEQ,
        dataset_text_field="text",
        bf16=True,
        seed=42,
    ),
    train_dataset=ds,
    tokenizer=tokenizer,
)

start = time.time()
trainer.train()
dur = time.time() - start

print(f"DONE in {dur:.0f}s")
model.save_pretrained(f"{RUN}/lora")
tokenizer.save_pretrained(f"{RUN}/lora")

manifest = {
    "name": "mascarade-cpt-code",
    "stage": "CPT (continued pre-training)",
    "base_model": BASE_MODEL,
    "dataset": DATASET,
    "examples": len(ds),
    "epochs": 1,
    "lr": 5e-5,
    "lora_r": 32,
    "seq_length": SEQ,
    "duration_seconds": dur,
    "output_dir": RUN,
    "next_stage": "SFT on domain-specific Q&A datasets",
}
json.dump(manifest, open(f"{RUN}/manifest.json", "w"), indent=2)
print(f"Output: {RUN}")
print("Next: use this LoRA as base for SFT mini-models")
