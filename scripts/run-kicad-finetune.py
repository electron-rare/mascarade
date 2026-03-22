"""T-MA-016: Fine-tune Mistral Small on KiCad dataset."""

import json
import time
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

print("=== T-MA-016: KiCad Fine-tune ===")
print("Loading model...")

from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

RUN_DIR = f"finetune/runs/kicad-tma016-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(RUN_DIR, exist_ok=True)

# Load model with QLoRA 4-bit
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Mistral-Small-3.1-24B-Instruct-2503-unsloth-bnb-4bit",
    max_seq_length=2048,
    load_in_4bit=True,
)

# Apply LoRA
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

# Load dataset
dataset = load_dataset("json", data_files="finetune/datasets/kicad_chat.jsonl", split="train")
print(f"Dataset loaded: {len(dataset)} examples")

# Format conversations
def format_chat(example):
    convs = example.get("conversations", [])
    text = ""
    for msg in convs:
        role = msg.get("role", msg.get("from", ""))
        content = msg.get("content", msg.get("value", ""))
        if role in ("system", "human", "user"):
            text += f"<s>[INST] {content} [/INST]"
        elif role in ("assistant", "gpt"):
            text += f" {content}</s>"
    return {"text": text}

dataset = dataset.map(format_chat)

# Training
training_args = SFTConfig(
    output_dir=RUN_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16,
    learning_rate=2e-4,
    warmup_steps=50,
    logging_steps=10,
    save_steps=200,
    max_seq_length=2048,
    dataset_text_field="text",
    bf16=True,
    seed=42,
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    tokenizer=tokenizer,
)

print(f"Starting training... Output: {RUN_DIR}")
start = time.time()
trainer.train()
duration = time.time() - start

print(f"=== DONE in {duration:.0f}s ===")

# Save LoRA
model.save_pretrained(f"{RUN_DIR}/lora")
tokenizer.save_pretrained(f"{RUN_DIR}/lora")
print("LoRA adapter saved")

# Manifest
manifest = {
    "task": "T-MA-016",
    "base_model": "Mistral-Small-3.1-24B-Instruct",
    "dataset": "kicad_chat.jsonl",
    "examples": len(dataset),
    "epochs": 3,
    "duration_seconds": duration,
    "output_dir": RUN_DIR,
}
with open(f"{RUN_DIR}/manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest: {RUN_DIR}/manifest.json")
