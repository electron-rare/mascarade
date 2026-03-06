#!/usr/bin/env python3
"""Local fine-tuning script for Quadro P2000 (5GB VRAM).

Reads ShareGPT JSONL datasets and trains with QLoRA on TinyLlama-1.1B.

Usage:
  python train_local.py stm32           # Train on STM32 dataset
  python train_local.py kicad           # Train on KiCad dataset
  python train_local.py all             # Train all domains sequentially
  python train_local.py stm32 --eval    # Evaluate after training
  python train_local.py stm32 --model Qwen/Qwen2.5-Coder-1.5B
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
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(SCRIPT_DIR, "datasets")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "models_local")

DOMAINS = ["stm32", "spice", "iot", "power", "dsp", "emc", "kicad", "embedded"]

DEFAULT_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

# LoRA targets per model architecture
LORA_TARGETS = {
    "tinyllama": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "qwen": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "llama": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "gpt2": ["c_attn"],
    "phi": ["q_proj", "v_proj", "k_proj", "dense"],
}


def detect_lora_targets(model_name: str) -> list[str]:
    name = model_name.lower()
    for key, targets in LORA_TARGETS.items():
        if key in name:
            return targets
    return ["q_proj", "v_proj"]


def load_sharegpt_jsonl(path: str, max_samples: int | None = None) -> list[str]:
    """Convert ShareGPT JSONL to formatted chat strings."""
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
    domain: str,
    model_name: str = DEFAULT_MODEL,
    max_seq_len: int = 512,
    epochs: int = 3,
    max_samples: int | None = None,
    do_eval: bool = False,
):
    dataset_path = os.path.join(DATASETS_DIR, f"{domain}_chat.jsonl")
    if not os.path.exists(dataset_path):
        print(f"Dataset not found: {dataset_path}")
        return False

    output_dir = os.path.join(OUTPUT_DIR, domain)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Domain: {domain}")
    print(f"  Model:  {model_name}")
    print(f"  Seq:    {max_seq_len}")
    print(f"  Epochs: {epochs}")
    print(f"{'='*60}")

    # Free GPU memory
    gc.collect()
    torch.cuda.empty_cache()

    # 1. Load dataset
    print("\n[1/5] Loading dataset...")
    texts = load_sharegpt_jsonl(dataset_path, max_samples)
    print(f"  {len(texts)} conversations loaded")

    # 2. Load tokenizer
    print("\n[2/5] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Tokenize
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

    # 3. Load model with 4-bit quantization
    print("\n[3/5] Loading model (4-bit quantized)...")
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    mem_mb = torch.cuda.memory_allocated() / 1024**2
    print(f"  Model loaded: {mem_mb:.0f} MB GPU")

    # 4. Configure LoRA
    print("\n[4/5] Configuring LoRA...")
    targets = detect_lora_targets(model_name)
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=targets,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 5. Train
    print("\n[5/5] Training...")
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=50,
        fp16=True,
        optim="paged_adamw_8bit",
        logging_steps=25,
        save_steps=500,
        save_total_limit=2,
        eval_strategy="steps" if len(tokenized["test"]) > 0 else "no",
        eval_steps=500,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        load_best_model_at_end=False,
        dataloader_pin_memory=False,
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

    # Save LoRA adapter
    adapter_path = os.path.join(output_dir, "adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"  Adapter saved: {adapter_path}")

    # Save training info
    info = {
        "domain": domain,
        "model": model_name,
        "samples": len(texts),
        "epochs": epochs,
        "max_seq_len": max_seq_len,
        "loss": result.training_loss,
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_targets": targets,
    }
    with open(os.path.join(output_dir, "training_info.json"), "w") as f:
        json.dump(info, f, indent=2)

    # Eval
    if do_eval:
        evaluate(model, tokenizer, domain)

    # Cleanup
    del model, trainer
    gc.collect()
    torch.cuda.empty_cache()

    print(f"\n  {domain} done!")
    return True


def evaluate(model, tokenizer, domain: str):
    prompts = {
        "stm32": "Configure SPI1 on STM32F4 for full-duplex communication at 1MHz.",
        "kicad": "How to set up controlled impedance routing in KiCad 8?",
        "spice": "Write a SPICE netlist for a common-emitter amplifier with bypass capacitor.",
        "iot": "Write ESP-IDF code to connect to WiFi and publish MQTT data.",
        "power": "Design a 12V to 5V buck converter with 2A output.",
        "dsp": "Implement a 4th order Butterworth low-pass filter in C.",
        "emc": "What decoupling capacitor values for a 100MHz digital IC?",
        "embedded": "Write bare-metal SysTick timer init for ARM Cortex-M4.",
    }
    prompt = prompts.get(domain, prompts["stm32"])

    print(f"\n  Eval prompt: {prompt}")
    formatted = f"<|system|>\nYou are an expert engineer.</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"

    inputs = tokenizer(formatted, return_tensors="pt").to("cuda")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
        )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"  Response:\n{response[len(formatted):][:500]}")


def main():
    parser = argparse.ArgumentParser(description="Local fine-tuning on P2000")
    parser.add_argument("domain", choices=DOMAINS + ["all"], help="Domain to train")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Base model")
    parser.add_argument("--seq-len", type=int, default=512, help="Max sequence length")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--max-samples", type=int, default=None, help="Limit samples")
    parser.add_argument("--eval", action="store_true", help="Evaluate after training")
    args = parser.parse_args()

    domains = DOMAINS if args.domain == "all" else [args.domain]

    for domain in domains:
        success = train_domain(
            domain=domain,
            model_name=args.model,
            max_seq_len=args.seq_len,
            epochs=args.epochs,
            max_samples=args.max_samples,
            do_eval=args.eval,
        )
        if not success:
            print(f"  Skipping {domain}")


if __name__ == "__main__":
    main()
