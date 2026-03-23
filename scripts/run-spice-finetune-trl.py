"""T-MA-017: Fine-tune Qwen3-8B on SPICE+embedded — TRL/PEFT (no Unsloth)."""

import json
import time
import os
import torch

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

print("=== T-MA-017: SPICE+Embedded Fine-tune (TRL/PEFT) ===")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Free VRAM: {torch.cuda.mem_get_info()[0] // 1024**2} MB")

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset, concatenate_datasets

RUN_DIR = f"finetune/runs/spice-tma017-{time.strftime('%Y%m%d-%H%M%S')}"
os.makedirs(RUN_DIR, exist_ok=True)

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

# 4-bit quantization
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

print(f"Loading {MODEL_NAME}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)

model = prepare_model_for_kbit_training(model)

# LoRA config
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# Load datasets
datasets_files = [
    "finetune/datasets/spice_chat.jsonl",
    "finetune/datasets/embedded_chat.jsonl",
    "finetune/datasets/platformio_chat.jsonl",
    "finetune/datasets/stm32_chat.jsonl",
]

all_datasets = []
for f in datasets_files:
    if os.path.exists(f):
        ds = load_dataset("json", data_files=f, split="train")
        print(f"  {f}: {len(ds)} examples")
        all_datasets.append(ds)

dataset = concatenate_datasets(all_datasets)
print(f"Total dataset: {len(dataset)} examples")


# Format conversations
def format_chat(example):
    convs = example.get("conversations", [])
    text = ""
    for msg in convs:
        role = msg.get("role", msg.get("from", ""))
        content = msg.get("content", msg.get("value", ""))
        if role in ("system", "human", "user"):
            text += f"<|im_start|>user\n{content}<|im_end|>\n"
        elif role in ("assistant", "gpt"):
            text += f"<|im_start|>assistant\n{content}<|im_end|>\n"
    return {"text": text}


dataset = dataset.map(format_chat)

# Training
training_args = SFTConfig(
    output_dir=RUN_DIR,
    num_train_epochs=2,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16,
    learning_rate=1e-4,
    warmup_steps=100,
    logging_steps=25,
    save_steps=500,
    max_seq_length=2048,
    dataset_text_field="text",
    bf16=True,
    seed=42,
    gradient_checkpointing=True,
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

model.save_pretrained(f"{RUN_DIR}/lora")
tokenizer.save_pretrained(f"{RUN_DIR}/lora")
print("LoRA adapter saved")

manifest = {
    "task": "T-MA-017",
    "base_model": MODEL_NAME,
    "datasets": datasets_files,
    "total_examples": len(dataset),
    "epochs": 2,
    "duration_seconds": duration,
    "output_dir": RUN_DIR,
    "method": "trl-peft-qlora-4bit",
}
with open(f"{RUN_DIR}/manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest: {RUN_DIR}/manifest.json")
