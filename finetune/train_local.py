#!/usr/bin/env python3
# ruff: noqa: E402
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
import sys
import warnings

if "--quiet" in sys.argv:
    warnings.filterwarnings("ignore")

from runtime_compat import disable_broken_torchvision

_RUNTIME_COMPAT_NOTE = disable_broken_torchvision()

import torch
from datasets import Dataset
from datasets.utils.logging import disable_progress_bar, enable_progress_bar
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from transformers.trainer_callback import PrinterCallback
from transformers.utils import logging as transformers_logging
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(SCRIPT_DIR, "datasets")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "models_local")

DOMAINS = [
    "stm32",
    "spice",
    "iot",
    "power",
    "dsp",
    "emc",
    "kicad",
    "embedded",
    "platformio",
    "freecad",
]

DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"

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


def format_chat(convos: list[dict], model_name: str) -> str:
    """Format conversations using the right chat template for the model."""
    name_lower = model_name.lower()
    parts = []
    if "qwen" in name_lower:
        for msg in convos:
            role = {"system": "system", "human": "user", "gpt": "assistant"}.get(
                msg["from"], msg["from"]
            )
            parts.append(f"<|im_start|>{role}\n{msg['value']}<|im_end|>")
    elif "tinyllama" in name_lower or "llama" in name_lower:
        for msg in convos:
            role = msg["from"]
            if role == "system":
                parts.append(f"<|system|>\n{msg['value']}</s>")
            elif role == "human":
                parts.append(f"<|user|>\n{msg['value']}</s>")
            elif role == "gpt":
                parts.append(f"<|assistant|>\n{msg['value']}</s>")
    else:
        # Generic chatml
        for msg in convos:
            role = {"system": "system", "human": "user", "gpt": "assistant"}.get(
                msg["from"], msg["from"]
            )
            parts.append(f"<|im_start|>{role}\n{msg['value']}<|im_end|>")
    return "\n".join(parts)


def load_sharegpt_jsonl(
    path: str, max_samples: int | None = None, model_name: str = DEFAULT_MODEL
) -> list[str]:
    """Convert ShareGPT JSONL to formatted chat strings."""
    texts = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break
            row = json.loads(line)
            convos = row.get("conversations", [])
            if convos:
                texts.append(format_chat(convos, model_name))
    return texts


def configure_runtime_logging(verbose: bool, quiet: bool) -> None:
    if quiet:
        disable_progress_bar()
        transformers_logging.set_verbosity_error()
    else:
        enable_progress_bar()
        (
            transformers_logging.set_verbosity_info()
            if verbose
            else transformers_logging.set_verbosity_warning()
        )


def resolve_tokenize_workers(requested: int | None, sample_count: int) -> int:
    if sample_count < 32:
        return 1
    if requested is None or requested <= 0:
        cpu_count = os.cpu_count() or 1
        requested = min(4, max(1, cpu_count // 2))
    return max(1, min(requested, sample_count))


def train_domain(
    domain: str,
    model_name: str = DEFAULT_MODEL,
    max_seq_len: int = 512,
    epochs: int = 3,
    max_samples: int | None = None,
    do_eval: bool = False,
    dataset_path: str | None = None,
    output_dir: str | None = None,
    verbose: bool = False,
    quiet: bool = False,
    tokenize_workers: int | None = None,
):
    configure_runtime_logging(verbose, quiet)

    def emit(message: str, *, important: bool = False) -> None:
        if quiet and not important:
            return
        print(message)

    dataset_path = dataset_path or os.path.join(DATASETS_DIR, f"{domain}_chat.jsonl")
    if not os.path.exists(dataset_path):
        emit(f"Dataset not found: {dataset_path}", important=True)
        return False

    if not torch.cuda.is_available():
        emit(
            "CUDA is not available. Use train_cpu.py or run_local.py --device cpu.",
            important=True,
        )
        return False

    output_dir = output_dir or os.path.join(OUTPUT_DIR, domain)
    os.makedirs(output_dir, exist_ok=True)

    if quiet:
        emit(
            f"[RUN] domain={domain} device=gpu model={model_name} seq={max_seq_len} epochs={epochs}",
            important=True,
        )
    else:
        emit(f"\n{'='*60}", important=True)
        emit(f"  Domain: {domain}", important=True)
        emit(f"  Model:  {model_name}", important=True)
        emit(f"  Seq:    {max_seq_len}", important=True)
        emit(f"  Epochs: {epochs}", important=True)
        if verbose:
            emit(f"  Dataset: {dataset_path}", important=True)
            emit(f"  Output:  {output_dir}", important=True)
        emit(f"{'='*60}", important=True)

    # Free GPU memory
    gc.collect()
    torch.cuda.empty_cache()

    # 1. Load dataset
    emit("\n[1/5] Loading dataset...")
    texts = load_sharegpt_jsonl(dataset_path, max_samples, model_name=model_name)
    emit(f"  {len(texts)} conversations loaded", important=verbose)

    # 2. Load tokenizer
    emit("\n[2/5] Loading tokenizer...")
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
    if len(dataset) < 2:
        raise ValueError(f"Dataset {dataset_path} needs at least 2 samples to train.")

    test_size = 1 if len(dataset) < 20 else max(1, int(len(dataset) * 0.05))
    split = dataset.train_test_split(test_size=test_size, seed=42)
    resolved_tokenize_workers = resolve_tokenize_workers(tokenize_workers, len(dataset))
    if resolved_tokenize_workers > 1:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    map_kwargs = {
        "batched": True,
        "remove_columns": ["text"],
    }
    if resolved_tokenize_workers > 1:
        map_kwargs["num_proc"] = resolved_tokenize_workers
    try:
        tokenized = split.map(tokenize, **map_kwargs)
    except Exception as exc:
        if resolved_tokenize_workers <= 1:
            raise
        emit(
            f"[WARN] tokenize workers fallback to 1 ({exc.__class__.__name__}: {exc})",
            important=True,
        )
        tokenized = split.map(tokenize, batched=True, remove_columns=["text"])
        resolved_tokenize_workers = 1
    emit(
        f"  Train: {len(tokenized['train'])}, Test: {len(tokenized['test'])}",
        important=verbose,
    )
    emit(f"  Tokenize workers: {resolved_tokenize_workers}", important=verbose)

    # 3. Load model with 4-bit quantization
    emit("\n[3/5] Loading model (4-bit quantized)...")
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
    model.config.use_cache = False

    mem_mb = torch.cuda.memory_allocated() / 1024**2
    emit(f"  Model loaded: {mem_mb:.0f} MB GPU", important=verbose)

    # 4. Configure LoRA
    emit("\n[4/5] Configuring LoRA...")
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
    if quiet:
        emit(f"  LoRA targets: {', '.join(targets)}", important=verbose)
    else:
        model.print_trainable_parameters()

    # 5. Train
    emit("\n[5/5] Training...")
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
        logging_strategy="no" if quiet else "steps",
        save_steps=500,
        save_total_limit=2,
        eval_strategy="steps" if len(tokenized["test"]) > 0 else "no",
        eval_steps=500,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        load_best_model_at_end=False,
        dataloader_pin_memory=False,
        disable_tqdm=quiet,
        log_level="error" if quiet else ("info" if verbose else "warning"),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["test"],
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    if quiet:
        trainer.remove_callback(PrinterCallback)

    result = trainer.train()
    emit(f"\n  Training loss: {result.training_loss:.4f}", important=True)

    # Save LoRA adapter
    adapter_path = os.path.join(output_dir, "adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    emit(f"  Adapter saved: {adapter_path}", important=True)

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
        evaluate(model, tokenizer, domain, model_name=model_name, quiet=quiet)

    # Cleanup
    del model, trainer
    gc.collect()
    torch.cuda.empty_cache()

    emit(f"\n  {domain} done!", important=True)
    return True


def evaluate(
    model, tokenizer, domain: str, model_name: str = DEFAULT_MODEL, quiet: bool = False
):
    prompts = {
        "stm32": "Configure SPI1 on STM32F4 for full-duplex communication at 1MHz.",
        "kicad": "How to set up controlled impedance routing in KiCad 8?",
        "spice": "Write a SPICE netlist for a common-emitter amplifier with bypass capacitor.",
        "iot": "Write ESP-IDF code to connect to WiFi and publish MQTT data.",
        "power": "Design a 12V to 5V buck converter with 2A output.",
        "dsp": "Implement a 4th order Butterworth low-pass filter in C.",
        "emc": "What decoupling capacitor values for a 100MHz digital IC?",
        "embedded": "Write bare-metal SysTick timer init for ARM Cortex-M4.",
        "platformio": "Write a platformio.ini for ESP32 with WiFiManager and MQTT libraries.",
        "freecad": "Write a FreeCAD Python script for a parametric mounting bracket.",
    }
    prompt = prompts.get(domain, prompts["stm32"])

    if not quiet:
        print(f"\n  Eval prompt: {prompt}")
    formatted = (
        format_chat(
            [
                {"from": "system", "value": "You are an expert engineer."},
                {"from": "human", "value": prompt},
            ],
            model_name if isinstance(model_name, str) else DEFAULT_MODEL,
        )
        + "\n"
    )

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
    parser.add_argument(
        "--dataset-path",
        default=None,
        help="Override ShareGPT JSONL dataset path",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output directory for checkpoints and adapters",
    )
    parser.add_argument(
        "--tokenize-workers",
        type=int,
        default=0,
        help="CPU workers for tokenization (0=auto)",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", action="store_true", help="Print detailed progress information"
    )
    verbosity.add_argument(
        "--quiet",
        action="store_true",
        help="Keep output minimal and hide progress bars",
    )
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
            dataset_path=args.dataset_path,
            output_dir=args.output_dir,
            verbose=args.verbose,
            quiet=args.quiet,
            tokenize_workers=args.tokenize_workers,
        )
        if not success:
            print(f"  Skipping {domain}")


if __name__ == "__main__":
    main()
