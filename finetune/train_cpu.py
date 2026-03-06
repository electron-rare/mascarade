#!/usr/bin/env python3
"""CPU-only fine-tuning script (runs in parallel with GPU training).

Uses GPT-2 124M (no quantization needed, ~500MB RAM).

Usage:
  python train_cpu.py kicad
  python train_cpu.py spice --epochs 2
  python train_cpu.py all
"""

import argparse
import json
import os
import gc

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(SCRIPT_DIR, "datasets")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "models_cpu")

DOMAINS = ["stm32", "spice", "iot", "power", "dsp", "emc", "kicad", "embedded"]

# GPT-2 fits easily in RAM without quantization
MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"


def load_sharegpt_jsonl(path: str, max_samples: int | None = None) -> list[str]:
    texts = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break
            row = json.loads(line)
            convos = row.get("conversations", [])
            parts = []
            for msg in convos:
                role = msg["from"]
                value = msg["value"]
                if role == "system":
                    parts.append(f"<|system|>\n{value}</s>")
                elif role == "human":
                    parts.append(f"<|user|>\n{value}</s>")
                elif role == "gpt":
                    parts.append(f"<|assistant|>\n{value}</s>")
            if parts:
                texts.append("\n".join(parts))
    return texts


def train_domain(
    domain: str, epochs: int = 3, max_samples: int | None = None, max_seq_len: int = 256
):
    dataset_path = os.path.join(DATASETS_DIR, f"{domain}_chat.jsonl")
    if not os.path.exists(dataset_path):
        print(f"Dataset not found: {dataset_path}")
        return False

    output_dir = os.path.join(OUTPUT_DIR, domain)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Domain: {domain} (CPU)")
    print(f"  Model:  {MODEL_NAME}")
    print(f"  Seq:    {max_seq_len}")
    print(f"  Epochs: {epochs}")
    print(f"{'='*60}")

    # 1. Load dataset
    print("\n[1/5] Loading dataset...")
    texts = load_sharegpt_jsonl(dataset_path, max_samples)
    print(f"  {len(texts)} conversations")

    # 2. Tokenizer
    print("\n[2/5] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def tokenize(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_seq_len,
            padding="max_length",
        )

    dataset = Dataset.from_dict({"text": texts})
    split = dataset.train_test_split(test_size=0.05, seed=42)
    tokenized = split.map(tokenize, batched=True, remove_columns=["text"])
    print(f"  Train: {len(tokenized['train'])}, Test: {len(tokenized['test'])}")

    # 3. Load model on CPU (no quantization)
    print("\n[3/5] Loading model on CPU (BF16)...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
        trust_remote_code=True,
    )

    # 4. LoRA
    print("\n[4/5] Configuring LoRA...")
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 5. Train
    print("\n[5/5] Training on CPU...")
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=30,
        bf16=False,  # CPU doesn't always support bf16 in trainer
        fp16=False,
        optim="adamw_torch",
        logging_steps=10,
        save_steps=200,
        save_total_limit=2,
        eval_strategy="no",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        load_best_model_at_end=False,
        dataloader_num_workers=4,
        no_cuda=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["test"],
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    result = trainer.train()
    print(f"\n  Training loss: {result.training_loss:.4f}")

    adapter_path = os.path.join(output_dir, "adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"  Adapter saved: {adapter_path}")

    info = {
        "domain": domain,
        "model": MODEL_NAME,
        "device": "cpu",
        "samples": len(texts),
        "epochs": epochs,
        "max_seq_len": max_seq_len,
        "loss": result.training_loss,
        "lora_r": 8,
        "lora_alpha": 16,
    }
    with open(os.path.join(output_dir, "training_info.json"), "w") as f:
        json.dump(info, f, indent=2)

    del model, trainer
    gc.collect()
    print(f"\n  {domain} done!")
    return True


def main():
    parser = argparse.ArgumentParser(description="CPU fine-tuning")
    parser.add_argument("domain", choices=DOMAINS + ["all"])
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--seq-len", type=int, default=256)
    args = parser.parse_args()

    # Force CPU
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    domains = DOMAINS if args.domain == "all" else [args.domain]
    for domain in domains:
        train_domain(domain, args.epochs, args.max_samples, args.seq_len)


if __name__ == "__main__":
    main()
