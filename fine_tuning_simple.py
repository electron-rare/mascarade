#!/usr/bin/env python3
# ruff: noqa: E402
"""
Simplified Fine-Tuning Script for Limited VRAM (Quadro P2000 - 4.9GB)
Uses only safetensors-compatible models to avoid PyTorch 2.2 vulnerabilities
"""

import os
import torch
from finetune.runtime_compat import disable_broken_torchvision

_RUNTIME_COMPAT_NOTE = disable_broken_torchvision()

from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from peft import LoraConfig, get_peft_model
from datasets import load_dataset
import warnings

warnings.filterwarnings("ignore")

# Configuration for Quadro P2000 (4.9GB VRAM)
# Using completely open-source model with safetensors
CONFIG = {
    "model_name": "openlm-research/open_llama_3b_v2",  # 3B parameters, fully open-source
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.1,
    "max_seq_length": 256,  # Reduced for memory
    "batch_size": 1,  # Must be 1 for 4.9GB VRAM
    "gradient_accumulation_steps": 32,  # Compensate for small batch
    "learning_rate": 3e-4,
    "output_dir": "./fine_tuned_simple",
}


def main():
    print("=" * 60)
    print("🎯 SIMPLE FINE-TUNING FOR LIMITED VRAM")
    print("=" * 60)
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print("=" * 60)

    # Set memory optimization
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    # Load tokenizer
    print("\n🔄 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])
    tokenizer.pad_token = tokenizer.eos_token

    # Load model - NO QUANTIZATION (avoids compatibility issues)
    print("🔄 Loading model (this may take a while)...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            CONFIG["model_name"],
            device_map="auto",
            torch_dtype=torch.float16,  # Use FP16 to save memory
            trust_remote_code=True,
        )
        print("✓ Model loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        return

    # Configure LoRA
    print("\n🔧 Configuring LoRA...")
    lora_config = LoraConfig(
        r=CONFIG["lora_r"],
        lora_alpha=CONFIG["lora_alpha"],
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=CONFIG["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    print(f"✓ LoRA configured: {model.print_trainable_parameters()}")

    # Prepare dataset
    print("\n📚 Preparing dataset...")
    try:
        # Create simple sample dataset
        samples = [
            "def hello_world():",
            "    print('Hello, World!')",
            "def add(a, b):",
            "    return a + b",
        ] * 10  # Repeat to have enough samples

        with open("simple_dataset.txt", "w") as f:
            f.write("\n\n".join(samples))

        dataset = load_dataset("text", data_files={"train": "simple_dataset.txt"})

        def tokenize_function(examples):
            return tokenizer(
                examples["text"],
                truncation=True,
                max_length=CONFIG["max_seq_length"],
                padding="max_length",
            )

        tokenized_datasets = dataset["train"].map(
            tokenize_function, batched=True, remove_columns=["text"]
        )

        print(f"✓ Dataset prepared: {len(tokenized_datasets)} samples")

    except Exception as e:
        print(f"✗ Failed to prepare dataset: {e}")
        return

    # Training arguments - optimized for 4.9GB VRAM
    print("\n🏋️ Starting training...")
    training_args = TrainingArguments(
        output_dir=CONFIG["output_dir"],
        per_device_train_batch_size=CONFIG["batch_size"],
        gradient_accumulation_steps=CONFIG["gradient_accumulation_steps"],
        learning_rate=CONFIG["learning_rate"],
        num_train_epochs=1,
        save_steps=50,
        logging_steps=10,
        fp16=True,
        optim="adamw_torch",  # Use regular AdamW to avoid issues
        lr_scheduler_type="linear",
        warmup_steps=50,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    # Train
    try:
        from transformers import Trainer

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_datasets,
            data_collator=lambda data: {
                "input_ids": torch.stack([f["input_ids"] for f in data]),
                "attention_mask": torch.stack([f["attention_mask"] for f in data]),
                "labels": torch.stack([f["input_ids"] for f in data]),
            },
        )

        train_result = trainer.train()

        # Save model
        os.makedirs(CONFIG["output_dir"], exist_ok=True)
        model.save_pretrained(CONFIG["output_dir"])
        tokenizer.save_pretrained(CONFIG["output_dir"])

        print("\n✓ Training completed!")
        print(f"  Model saved to: {CONFIG['output_dir']}")
        print(f"  Final loss: {train_result.metrics.get('train_loss', 'N/A')}")

    except Exception as e:
        print(f"✗ Training failed: {e}")
        return

    # Test inference
    print("\n🧪 Testing inference...")
    try:
        input_text = "def fibonacci("
        inputs = tokenizer(input_text, return_tensors="pt").to("cuda")
        outputs = model.generate(**inputs, max_new_tokens=50, temperature=0.7)
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"Input: {input_text}")
        print(f"Output: {result}")
    except Exception as e:
        print(f"✗ Inference failed: {e}")

    print("\n" + "=" * 60)
    print("🎉 FINE-TUNING COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    # Check GPU
    if not torch.cuda.is_available():
        print("⚠️  CUDA not available, exiting")
        exit(1)

    main()
