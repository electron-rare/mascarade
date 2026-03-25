"""Mega Finetune v2: Train on 500K electronics dataset."""

import json
import time
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["WANDB_DISABLED"] = "true"

print("=== MEGA FINETUNE v2: 500K Electronics Dataset ===")

from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

RUN_DIR = f"finetune/runs/mega-v2-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(RUN_DIR, exist_ok=True)

DATASET = "finetune/datasets/mega_v2_all_electronics.jsonl"

# Use Qwen3-8B (fits in 24GB with QLoRA, good base for multi-domain)
print("Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen3-8B-unsloth-bnb-4bit",
    max_seq_length=2048,
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
    random_state=42,
)

# Load dataset — sample 50K for first run (full 500K would take days)
print(f"Loading dataset from {DATASET}...")
ds = load_dataset("json", data_files=DATASET, split="train")
print(f"Full dataset: {len(ds)} examples")

# Sample 50K balanced across domains
SAMPLE_SIZE = 50000
if len(ds) > SAMPLE_SIZE:
    ds = ds.shuffle(seed=42).select(range(SAMPLE_SIZE))
    print(f"Sampled: {SAMPLE_SIZE} examples")


# Format conversations
def format_chat(example):
    convs = example.get("conversations", [])
    text = ""
    for msg in convs:
        role = msg.get("from", msg.get("role", ""))
        content = msg.get("value", msg.get("content", ""))
        if not content:
            continue
        if role in ("system", "human", "user"):
            text += f"<s>[INST] {content} [/INST]"
        elif role in ("assistant", "gpt"):
            text += f" {content}</s>"
    return {"text": text}


ds = ds.map(format_chat)
# Filter empty
ds = ds.filter(lambda x: len(x["text"]) > 50)
print(f"After formatting: {len(ds)} examples")

# Training
training_args = SFTConfig(
    output_dir=RUN_DIR,
    num_train_epochs=1,  # 1 epoch on 50K = plenty
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16,
    learning_rate=1e-4,
    warmup_steps=100,
    logging_steps=50,
    save_steps=1000,
    max_seq_length=2048,
    dataset_text_field="text",
    bf16=True,
    seed=42,
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=ds,
    tokenizer=tokenizer,
)

print(f"Starting training... Output: {RUN_DIR}")
start = time.time()
trainer.train()
duration = time.time() - start

print(f"=== DONE in {duration:.0f}s ===")

model.save_pretrained(f"{RUN_DIR}/lora")
tokenizer.save_pretrained(f"{RUN_DIR}/lora")
print("LoRA adapter saved")

manifest = {
    "task": "mega-finetune-v2",
    "base_model": "Qwen3-8B",
    "dataset": DATASET,
    "sampled": SAMPLE_SIZE,
    "full_dataset_size": 498723,
    "epochs": 1,
    "lora_r": 32,
    "lora_alpha": 64,
    "duration_seconds": duration,
    "output_dir": RUN_DIR,
}
with open(f"{RUN_DIR}/manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest: {RUN_DIR}/manifest.json")
