#!/usr/bin/env python3
"""
Training script executed on the remote Vast.ai GPU instance.
Uploaded by vast_finetune.sh, runs QLoRA fine-tuning with full T4/3090/A100 VRAM.
"""

import argparse
import os
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset

# Models sized for 24GB+ VRAM (RTX 3090 / A100)
DOMAIN_MODELS = {
    "kicad": "codellama/CodeLlama-7b-hf",
    "stm32": "codellama/CodeLlama-7b-hf",
    "generic": "mistralai/Mistral-7B-v0.1",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain", default="stm32", choices=["kicad", "stm32", "generic"]
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", default="/workspace/output")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--seq-length", type=int, default=512)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    args = parser.parse_args()

    model_name = DOMAIN_MODELS[args.domain]
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"{'=' * 60}")
    print(f"Vast.ai Training - {args.domain}")
    print(f"Model: {model_name}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print(f"{'=' * 60}")

    # QLoRA 4-bit quantization
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    print(f"VRAM after load: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")

    # LoRA
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Dataset
    print("Preparing dataset...")
    dataset = load_dataset("text", data_files={"train": args.dataset})
    split = dataset["train"].train_test_split(test_size=0.1, seed=42)

    def tokenize(examples):
        out = tokenizer(
            examples["text"],
            truncation=True,
            max_length=args.seq_length,
            padding="max_length",
        )
        out["labels"] = out["input_ids"].copy()
        return out

    train_ds = split["train"].map(tokenize, batched=True, remove_columns=["text"])
    eval_ds = split["test"].map(tokenize, batched=True, remove_columns=["text"])
    print(f"Train: {len(train_ds)}, Eval: {len(eval_ds)}")

    # Training
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        eval_strategy="steps",
        eval_steps=100,
        save_steps=100,
        save_total_limit=2,
        logging_steps=10,
        bf16=True,
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    print("Starting training...")
    result = trainer.train()
    print(f"Training done. Loss: {result.metrics['train_loss']:.4f}")

    # Save
    save_path = os.path.join(args.output_dir, "final")
    model.save_pretrained(save_path)
    tokenizer.save_pretrained(save_path)
    print(f"Model saved to {save_path}")

    # Quick test
    print("\nTest inference:")
    prompts = {
        "kicad": "Generate a KiCad schematic for an LED circuit",
        "stm32": "Write STM32 HAL code for UART at 115200 baud",
        "generic": "Write a Python binary search function",
    }
    inputs = tokenizer(prompts[args.domain], return_tensors="pt").to("cuda")
    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=150, temperature=0.7, do_sample=True
        )
    print(tokenizer.decode(outputs[0], skip_special_tokens=True))


if __name__ == "__main__":
    main()
