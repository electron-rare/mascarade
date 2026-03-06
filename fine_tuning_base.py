#!/usr/bin/env python3
# ruff: noqa: E402
"""
Base Fine-Tuning Script for Multiple Domains
Optimized for limited VRAM (Quadro P2000 - 4.9GB)

Domains supported:
- KiCad/PCB/EDA
- STM32/FPGA
- Generic code/text

Features:
- LoRA adaptation for memory efficiency
- Gradient accumulation
- Mixed precision (FP16)
- Automatic checkpointing
- Domain-specific configurations
"""

import os
import json
import torch
from datetime import datetime
from finetune.runtime_compat import disable_broken_torchvision

_RUNTIME_COMPAT_NOTE = disable_broken_torchvision()

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset
from typing import Optional, Dict, Any

# Domain-specific configurations
# Using open-source models accessible without authentication
DOMAIN_CONFIGS = {
    "kicad": {
        "model_name": "codellama/CodeLlama-7b-hf",  # Excellent for code/EDA
        "lora_target_modules": ["q_proj", "v_proj"],
        "max_seq_length": 512,
        "batch_size": 2,  # Reduced for 7B model on 4.9GB VRAM
        "gradient_accumulation_steps": 16,
        "learning_rate": 2e-4,
        "description": "KiCad/PCB/EDA - Schematic and PCB design assistance",
    },
    "stm32": {
        "model_name": "codellama/CodeLlama-7b-hf",  # Best for C/assembly
        "lora_target_modules": ["q_proj", "v_proj"],
        "max_seq_length": 256,
        "batch_size": 2,  # Reduced for 7B model
        "gradient_accumulation_steps": 16,
        "learning_rate": 3e-4,
        "description": "STM32/FPGA - Embedded C, assembly, and HDL code",
    },
    "generic": {
        "model_name": "mistralai/Mistral-7B-v0.1",  # General purpose
        "lora_target_modules": ["q_proj", "v_proj"],
        "max_seq_length": 512,
        "batch_size": 2,  # Reduced for 7B model
        "gradient_accumulation_steps": 16,
        "learning_rate": 2e-4,
        "description": "Generic code/text - General programming and text",
    },
}

# Alternative smaller models for very limited VRAM
SMALL_MODEL_ALTERNATIVES = {
    "kicad": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",  # 1.1B parameters
    "stm32": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",  # 1.1B parameters
    "generic": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",  # 1.1B parameters
}

# Ultra-small models for extreme memory constraints
ULTRASMALL_MODEL_ALTERNATIVES = {
    "kicad": "gpt2",  # 124M parameters, safetensors compatible
    "stm32": "gpt2",  # 124M parameters, safetensors compatible
    "generic": "gpt2",  # 124M parameters, safetensors compatible
}


class FineTuningManager:
    """Main class for managing fine-tuning process"""

    def __init__(
        self, domain: str = "generic", output_dir: str = "./fine_tuned_models"
    ):
        """Initialize fine-tuning manager"""
        self.domain = domain.lower()
        self.config = DOMAIN_CONFIGS.get(self.domain, DOMAIN_CONFIGS["generic"])
        self.output_dir = os.path.join(output_dir, self.domain)
        self.model = None
        self.tokenizer = None
        self.trainer = None

        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)

        print(f"🚀 Initializing {self.domain} fine-tuning")
        print(f"📋 Configuration: {json.dumps(self.config, indent=2)}")

        # Save configuration
        with open(os.path.join(self.output_dir, "config.json"), "w") as f:
            json.dump(self.config, f, indent=2)

    def load_model(
        self,
        use_4bit: bool = True,
        use_8bit: bool = False,
        use_small: bool = False,
        use_ultrasmall: bool = False,
    ):
        """Load model with quantization for memory efficiency"""
        model_name = self.config["model_name"]

        # Use smaller alternative if requested
        if use_ultrasmall:
            model_name = ULTRASMALL_MODEL_ALTERNATIVES.get(
                self.domain, self.config["model_name"]
            )
            print(f"\n🔄 Loading ultra-small model: {model_name}")
            # GPT-2 uses different attention module names
            if "gpt2" in model_name:
                self.config["lora_target_modules"] = ["c_attn"]
        elif use_small:
            model_name = SMALL_MODEL_ALTERNATIVES.get(
                self.domain, self.config["model_name"]
            )
            print(f"\n🔄 Loading small model: {model_name}")
        else:
            print(f"\n🔄 Loading model: {model_name}")

        # Set memory optimization environment variable
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

        # Quantization configuration - critical for 4.9GB VRAM
        # Skip quantization for ultra-small models (GPT-2 124M fits in FP16 easily)
        quant_config = None
        if use_ultrasmall:
            print("  Skipping quantization (model small enough for FP16)")
        elif use_4bit:
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=False,
            )
        elif use_8bit:
            quant_config = BitsAndBytesConfig(
                load_in_8bit=True,
            )
        else:
            print(
                "⚠️  Warning: Running without quantization may cause OOM errors on 4.9GB VRAM"
            )

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quant_config,
                device_map="auto",
                trust_remote_code=True,
            )

            # Prepare for LoRA (only needed with quantization)
            if quant_config is not None:
                self.model = prepare_model_for_kbit_training(self.model)

            print("✓ Model loaded successfully")
            print(f"  Memory usage: {self._get_memory_usage()}")

            return True

        except Exception as e:
            print(f"✗ Failed to load model: {e}")
            return False

    def configure_lora(self, r: int = 8, alpha: int = 16, dropout: float = 0.1):
        """Configure LoRA adaptation"""
        print(f"\n🔧 Configuring LoRA (r={r}, alpha={alpha})")

        lora_config = LoraConfig(
            r=r,
            lora_alpha=alpha,
            target_modules=self.config["lora_target_modules"],
            lora_dropout=dropout,
            bias="none",
            task_type="CAUSAL_LM",
        )

        self.model = get_peft_model(self.model, lora_config)

        # Print trainable parameters
        trainable_params = self.model.print_trainable_parameters()
        print(f"✓ LoRA configured: {trainable_params}")

        return lora_config

    def prepare_dataset(self, dataset_path: str, test_size: float = 0.1):
        """Prepare dataset for training"""
        print(f"\n📚 Preparing dataset: {dataset_path}")

        try:
            # Load dataset
            dataset = load_dataset("text", data_files={"train": dataset_path})

            # Split train/test
            split_dataset = dataset["train"].train_test_split(test_size=test_size)

            # Tokenize function
            def tokenize_function(examples):
                return self.tokenizer(
                    examples["text"],
                    truncation=True,
                    max_length=self.config["max_seq_length"],
                    padding="max_length",
                )

            # Tokenize datasets
            tokenized_datasets = split_dataset.map(
                tokenize_function, batched=True, remove_columns=["text"]
            )

            print("✓ Dataset prepared:")
            print(f"  Train samples: {len(tokenized_datasets['train'])}")
            print(f"  Test samples: {len(tokenized_datasets['test'])}")

            return tokenized_datasets

        except Exception as e:
            print(f"✗ Failed to prepare dataset: {e}")
            return None

    def train(self, dataset, num_epochs: int = 3, save_steps: int = 500):
        """Train the model"""
        print(f"\n🏋️ Starting training for {num_epochs} epochs")

        # Training arguments optimized for limited VRAM
        training_args = TrainingArguments(
            output_dir=self.output_dir,
            per_device_train_batch_size=1,  # Force batch_size=1 for 4.9GB VRAM
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=self.config["gradient_accumulation_steps"]
            * 4,  # Compensate for smaller batch
            learning_rate=self.config["learning_rate"],
            num_train_epochs=num_epochs,
            save_steps=save_steps,
            save_total_limit=2,
            logging_steps=50,
            # Disable evaluation to save memory
            # eval_strategy="steps",
            # eval_steps=save_steps,
            fp16=torch.cuda.is_available(),  # Mixed precision (GPU only)
            optim="paged_adamw_8bit" if torch.cuda.is_available() else "adamw_torch",
            lr_scheduler_type="cosine",
            warmup_steps=100,
            report_to="none",
            load_best_model_at_end=False,  # Disable to save memory
            # metric_for_best_model="eval_loss",
            # greater_is_better=False,
            gradient_checkpointing=True,  # Enable gradient checkpointing
            gradient_checkpointing_kwargs={
                "use_reentrant": False
            },  # Avoid reentrant issues
            # Reduce sequence length for memory
            # Note: This is handled in dataset preparation
        )

        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer, mlm=False
        )

        # Initialize trainer
        from transformers import Trainer

        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["test"],
            data_collator=data_collator,
        )

        try:
            # Start training
            train_result = self.trainer.train()

            # Save final model
            self.trainer.save_model(os.path.join(self.output_dir, "final"))
            self.tokenizer.save_pretrained(os.path.join(self.output_dir, "final"))

            print("✓ Training completed!")
            print(f"  Final model saved to: {self.output_dir}/final")
            print(f"  Training metrics: {train_result.metrics}")

            return True

        except Exception as e:
            print(f"✗ Training failed: {e}")
            return False

    def evaluate(self, test_prompts: list = None):
        """Evaluate model on test prompts"""
        if test_prompts is None:
            test_prompts = [
                "Write a KiCad schematic for a simple LED circuit",
                "Generate STM32 code for UART communication",
                "Explain how to design a PCB for high-speed signals",
            ]

        print(f"\n🧪 Evaluating model with {len(test_prompts)} prompts")

        try:
            results = []
            for i, prompt in enumerate(test_prompts):
                inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")
                outputs = self.model.generate(
                    **inputs, max_new_tokens=100, temperature=0.7, do_sample=True
                )
                result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                results.append(result)
                print(f"\nPrompt {i+1}: {prompt}")
                print(f"Response: {result}")
                print("-" * 80)

            return results

        except Exception as e:
            print(f"✗ Evaluation failed: {e}")
            return None

    def save_model(self, output_path: Optional[str] = None):
        """Save the fine-tuned model"""
        save_path = output_path or os.path.join(
            self.output_dir, f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(save_path, exist_ok=True)

        print(f"\n💾 Saving model to: {save_path}")

        try:
            self.model.save_pretrained(save_path)
            self.tokenizer.save_pretrained(save_path)
            print("✓ Model saved successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to save model: {e}")
            return False

    def _get_memory_usage(self) -> str:
        """Get current GPU memory usage"""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**2  # MB
            reserved = torch.cuda.memory_reserved() / 1024**2  # MB
            return f"{allocated:.1f}MB allocated, {reserved:.1f}MB reserved"
        return "CUDA not available"

    def get_training_summary(self) -> Dict[str, Any]:
        """Get training summary"""
        return {
            "domain": self.domain,
            "model": self.config["model_name"],
            "timestamp": datetime.now().isoformat(),
            "gpu_info": {
                "name": (
                    torch.cuda.get_device_name(0)
                    if torch.cuda.is_available()
                    else "CPU"
                ),
                "memory": self._get_memory_usage(),
            },
            "configuration": self.config,
        }


def create_sample_dataset(domain: str, filename: str = "sample_dataset.txt"):
    """Create a small sample dataset for testing"""
    print(f"\n📝 Creating sample dataset for {domain}")

    samples = {
        "kicad": [
            "# KiCad Schematic Example\nEESchema Schematic File Version 4\nLIBS: power,device,conn\nEELAYER 25 0\nEELAYER END\n$Comp\nL LED LED_0805\nU 1 1 63C00000\nP 1000 2000\nAR Path='/1000 2000' Reference='D1' Value='LED'\n$EndComp\n",
            '# PCB Design Rules\n(rule "Clearance" (constraint pcb_text (min 0.2mm)))\n(rule "Track Width" (constraint track_width (min 0.25mm)))\n(rule "Via Diameter" (constraint via_diameter (min 0.8mm)))\n',
            '# Python script for KiCad automation\ndef generate_footprint(name, size):\n    # Create footprint\n    footprint = Footprint(name)\n    # Add pads\n    for i in range(2):\n        pad = Pad(i+1, "thru_hole", shape="rect", at=[i*size, 0], size=[1.5, 1.5], drill=0.8)\n        footprint.add(pad)\n    return footprint\n',
        ],
        "stm32": [
            '// STM32 GPIO Configuration\n#include "stm32f4xx_hal.h"\nvoid GPIO_Init(void) {\n  GPIO_InitTypeDef GPIO_InitStruct = {0};\n  __HAL_RCC_GPIOA_CLK_ENABLE();\n  GPIO_InitStruct.Pin = GPIO_PIN_5;\n  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;\n  GPIO_InitStruct.Pull = GPIO_NOPULL;\n  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;\n  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);\n}\n',
            "// UART Communication\nvoid UART_Transmit(char *data) {\n  HAL_UART_Transmit(&huart2, (uint8_t*)data, strlen(data), HAL_MAX_DELAY);\n}\nvoid UART_Receive(char *buffer, uint16_t size) {\n  HAL_UART_Receive(&huart2, (uint8_t*)buffer, size, HAL_MAX_DELAY);\n}\n",
            "// Assembly function for STM32\n.syntax unified\n.thumb\n.section .text\n.global fast_add\nfast_add:\n  ADD r0, r0, r1\n  BX lr\n.end\n",
        ],
        "generic": [
            "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)\n",
            "class BinaryTree:\n    def __init__(self, value):\n        self.value = value\n        self.left = None\n        self.right = None\n    def insert(self, value):\n        if value < self.value:\n            if self.left is None:\n                self.left = BinaryTree(value)\n            else:\n                self.left.insert(value)\n        else:\n            if self.right is None:\n                self.right = BinaryTree(value)\n            else:\n                self.right.insert(value)\n",
            "# REST API Example\nfrom flask import Flask, jsonify\napp = Flask(__name__)\n@app.route('/api/data', methods=['GET'])\ndef get_data():\n    return jsonify({'status': 'success', 'data': [1, 2, 3]})\nif __name__ == '__main__':\n    app.run(debug=True)\n",
        ],
    }

    domain_samples = samples.get(domain, samples["generic"])

    with open(filename, "w", encoding="utf-8") as f:
        for sample in domain_samples:
            f.write(sample + "\n\n" + "=" * 80 + "\n\n")

    print(f"✓ Sample dataset created: {filename}")
    print(f"  {len(domain_samples)} samples written")
    return filename


def main():
    """Main function"""
    print("=" * 80)
    print("🎯 MULTI-DOMAIN FINE-TUNING SCRIPT")
    print("=" * 80)
    print("Optimized for limited VRAM (Quadro P2000 - 4.9GB)")
    print("Domains: KiCad/EDA, STM32/FPGA, Generic Code")
    print("=" * 80)

    # Check GPU
    if not torch.cuda.is_available():
        print("⚠️  Warning: CUDA not available, using CPU (will be slow)")
    else:
        print(f"✓ GPU detected: {torch.cuda.get_device_name(0)}")
        print(
            f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB"
        )

    # Create sample datasets
    for domain in ["kicad", "stm32", "generic"]:
        create_sample_dataset(domain, f"sample_{domain}_dataset.txt")

    print("\n" + "=" * 80)
    print("📋 EXAMPLE USAGE")
    print("=" * 80)

    # Example for KiCad domain
    print("\n1. KiCad/EDA Example:")
    print("-" * 40)
    kicad_tuner = FineTuningManager("kicad")
    if kicad_tuner.load_model(use_4bit=True, use_small=False):
        kicad_tuner.configure_lora(r=8, alpha=16)
        print("  Model loaded and LoRA configured")
        print(
            "  Ready to train with: python fine_tuning_base.py --domain kicad --train"
        )
        print(
            "  For smaller model: python fine_tuning_base.py --domain kicad --train --small"
        )

    # Example for STM32 domain
    print("\n2. STM32/FPGA Example:")
    print("-" * 40)
    stm32_tuner = FineTuningManager("stm32")
    if stm32_tuner.load_model(use_4bit=True, use_small=False):
        stm32_tuner.configure_lora(r=16, alpha=32)
        print("  Model loaded and LoRA configured")
        print(
            "  Ready to train with: python fine_tuning_base.py --domain stm32 --train"
        )
        print(
            "  For smaller model: python fine_tuning_base.py --domain stm32 --train --small"
        )

    # Example for generic domain
    print("\n3. Generic Code Example:")
    print("-" * 40)
    generic_tuner = FineTuningManager("generic")
    if generic_tuner.load_model(use_4bit=True, use_small=False):
        generic_tuner.configure_lora(r=8, alpha=16)
        print("  Model loaded and LoRA configured")
        print(
            "  Ready to train with: python fine_tuning_base.py --domain generic --train"
        )
        print(
            "  For smaller model: python fine_tuning_base.py --domain generic --train --small"
        )

    print("\n" + "=" * 80)
    print("🎯 FINE-TUNING READY!")
    print("=" * 80)
    print("\n📋 USAGE:")
    print("  Train (7B model, 4-bit quant) - requires ~6GB VRAM:")
    print("    python fine_tuning_base.py --domain [kicad|stm32|generic] --train")
    print("\n  Train (1.1B model, 4-bit quant) - requires ~3GB VRAM:")
    print(
        "    python fine_tuning_base.py --domain [kicad|stm32|generic] --train --small"
    )
    print("\n  Train (33M model, 4-bit quant) - requires ~1GB VRAM:")
    print(
        "    python fine_tuning_base.py --domain [kicad|stm32|generic] --train --ultrasmall --short-seq"
    )
    print("\n  Evaluate:")
    print("    python fine_tuning_base.py --domain [kicad|stm32|generic] --evaluate")
    print("\n  Custom dataset:")
    print(
        "    python fine_tuning_base.py --domain kicad --train --small --dataset my_data.txt"
    )
    print("\n⚠️  Note: First run will download models (several GB)")
    print("⚠️  For Quadro P2000 (4.9GB): use --small or --ultrasmall")
    print("=" * 80)


if __name__ == "__main__":
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Domain Fine-Tuning Script")
    parser.add_argument(
        "--domain",
        type=str,
        choices=["kicad", "stm32", "generic"],
        default="generic",
        help="Domain to fine-tune",
    )
    parser.add_argument("--train", action="store_true", help="Start training")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate model")
    parser.add_argument(
        "--dataset", type=str, default=None, help="Path to custom dataset file"
    )
    parser.add_argument(
        "--epochs", type=int, default=3, help="Number of training epochs"
    )
    parser.add_argument(
        "--small", action="store_true", help="Use smaller model (1-2B parameters)"
    )
    parser.add_argument(
        "--ultrasmall",
        action="store_true",
        help="Use ultra-small model (33-100M parameters)",
    )
    parser.add_argument(
        "--no-quant", action="store_true", help="Disable quantization (not recommended)"
    )
    parser.add_argument(
        "--short-seq",
        action="store_true",
        help="Use shorter sequences (256 instead of 512)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None, help="Custom output directory"
    )

    args = parser.parse_args()

    if args.train or args.evaluate:
        # Initialize tuner
        output_dir = args.output_dir or "./fine_tuned_models"
        tuner = FineTuningManager(args.domain, output_dir=output_dir)

        # Load model with appropriate settings
        use_4bit = not args.no_quant
        use_small = args.small
        use_ultrasmall = args.ultrasmall

        if not tuner.load_model(
            use_4bit=use_4bit, use_small=use_small, use_ultrasmall=use_ultrasmall
        ):
            exit(1)

        # Adjust sequence length if requested
        if args.short_seq:
            tuner.config["max_seq_length"] = 256
            print(f"📏 Using shorter sequence length: {tuner.config['max_seq_length']}")

        # Configure LoRA
        tuner.configure_lora()

        if args.train:
            # Use sample dataset if none provided
            dataset_path = args.dataset or f"sample_{args.domain}_dataset.txt"

            # Prepare dataset
            dataset = tuner.prepare_dataset(dataset_path)
            if dataset:
                # Train
                tuner.train(dataset, num_epochs=args.epochs)

                # Save final model
                tuner.save_model()

        if args.evaluate:
            # Evaluate
            tuner.evaluate()
    else:
        # Show help/examples
        main()
