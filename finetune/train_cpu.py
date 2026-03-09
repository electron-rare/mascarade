#!/usr/bin/env python3
# ruff: noqa: E402
"""CPU-only fine-tuning script.

Optimized for a local fallback path when CUDA is unavailable. Uses the model
selected by model_selector.py if available, otherwise defaults to
Qwen/Qwen2.5-Coder-1.5B-Instruct.

Usage:
  python train_cpu.py kicad
  python train_cpu.py spice --epochs 2
  python train_cpu.py stm32 --model Qwen/Qwen2.5-Coder-1.5B-Instruct
  python train_cpu.py all
"""

import argparse
import json
import os
import gc
import sys
import warnings
from pathlib import Path

if "--quiet" in sys.argv:
    warnings.filterwarnings("ignore")

from llm_paths import configure_hf_env

configure_hf_env()

from dataset_quality import DatasetQualityError, enforce_dataset_quality, summarize_quality_report
from runtime_compat import disable_broken_torchvision
from sharegpt_utils import ensure_row_ids_with_stats, load_jsonl, validate_rows

_RUNTIME_COMPAT_NOTE = disable_broken_torchvision()

import torch
from datasets import Dataset
from datasets.utils.logging import disable_progress_bar, enable_progress_bar
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from transformers.trainer_callback import PrinterCallback
from transformers.utils import logging as transformers_logging
from peft import LoraConfig, get_peft_model

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
    "components",
]

try:
    from model_selector import resolve_model as _resolve

    DEFAULT_MODEL = _resolve("Qwen/Qwen2.5-Coder-1.5B-Instruct")
except Exception:
    DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"

LORA_TARGETS = {
    "gpt2": ["c_attn"],
    "tinyllama": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "qwen": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "llama": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "mistral": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "phi": ["q_proj", "v_proj", "k_proj", "dense"],
}

TEACHER_ONLY_STUDENT_PATTERNS = {
    "qwen/qwen3.5-35b-a3b-gptq-int4": (
        "teacher-only in this pipeline: GPTQ Int4 MoE checkpoint intended for inference/teacher use"
    ),
    "qwen/qwen3-next-80b-a3b-instruct-fp8": (
        "teacher-only in this pipeline: FP8 MoE checkpoint intended for serving/teacher use"
    ),
    "devstral-small-2507": (
        "teacher-only in this pipeline: Mistral coding teacher/inference model"
    ),
    "mistralai/devstral-small-2-24b-instruct-2512": (
        "teacher-only in this pipeline: recent Devstral local teacher/inference model"
    ),
    "mistral-small-3.1": (
        "teacher-only in this pipeline: Mistral teacher/inference model"
    ),
    "mistralai/mistral-small-3.1-24b-base-2503": (
        "teacher-only in this pipeline: recent Mistral 24B local teacher/inference model"
    ),
    "mistralai/mistral-small-3.2-24b-instruct-2506": (
        "teacher-only in this pipeline: recent Mistral 24B instruct local teacher/inference model"
    ),
}


def detect_lora_targets(model_name: str) -> list[str]:
    name = model_name.lower()
    for key, targets in LORA_TARGETS.items():
        if key in name:
            return targets
    return ["c_attn"]


def assert_supported_student_model(model_name: str) -> None:
    name = model_name.lower()
    for pattern, reason in TEACHER_ONLY_STUDENT_PATTERNS.items():
        if pattern in name:
            raise ValueError(f"Unsupported student model {model_name}: {reason}")


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
        for msg in convos:
            role = {"system": "system", "human": "user", "gpt": "assistant"}.get(
                msg["from"], msg["from"]
            )
            parts.append(f"<|im_start|>{role}\n{msg['value']}<|im_end|>")
    return "\n".join(parts)


def load_sharegpt_jsonl(
    path: str, max_samples: int | None = None, model_name: str = DEFAULT_MODEL
) -> list[str]:
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
    epochs: int = 3,
    max_samples: int | None = None,
    max_seq_len: int = 256,
    model_name: str = DEFAULT_MODEL,
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
    raw_rows = load_jsonl(Path(dataset_path))
    normalized_rows, normalized_source_ids = ensure_row_ids_with_stats(
        raw_rows, f"{domain}-dataset"
    )
    validation_errors = validate_rows(normalized_rows)
    if validation_errors:
        emit(
            f"Dataset is invalid ({len(validation_errors)} errors): {validation_errors[0]}",
            important=True,
        )
        return False
    try:
        dataset_quality = enforce_dataset_quality(
            normalized_rows,
            label=f"{domain} dataset",
            ids_fixed=normalized_source_ids,
        )
    except DatasetQualityError as exc:
        emit(f"Dataset quality gate failed: {exc}", important=True)
        return False
    if dataset_quality["warnings"]:
        emit(
            f"[WARN] dataset-quality: {summarize_quality_report(dataset_quality)}",
            important=True,
        )

    output_dir = output_dir or os.path.join(OUTPUT_DIR, domain)
    os.makedirs(output_dir, exist_ok=True)
    assert_supported_student_model(model_name)

    if quiet:
        emit(
            f"[RUN] domain={domain} device=cpu model={model_name} seq={max_seq_len} epochs={epochs}",
            important=True,
        )
    else:
        emit(f"\n{'='*60}", important=True)
        emit(f"  Domain: {domain} (CPU)", important=True)
        emit(f"  Model:  {model_name}", important=True)
        emit(f"  Seq:    {max_seq_len}", important=True)
        emit(f"  Epochs: {epochs}", important=True)
        if verbose:
            emit(f"  Dataset: {dataset_path}", important=True)
            emit(f"  Output:  {output_dir}", important=True)
        emit(f"{'='*60}", important=True)

    # 1. Load dataset
    emit("\n[1/5] Loading dataset...")
    texts = load_sharegpt_jsonl(dataset_path, max_samples, model_name=model_name)
    emit(f"  {len(texts)} conversations", important=verbose)

    # 2. Tokenizer
    emit("\n[2/5] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
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

    # 3. Load model on CPU (no quantization)
    emit("\n[3/5] Loading model on CPU...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )
    model.to("cpu")
    model.config.use_cache = False

    # 4. LoRA
    emit("\n[4/5] Configuring LoRA...")
    targets = detect_lora_targets(model_name)
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
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
    emit("\n[5/5] Training on CPU...")
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
        logging_strategy="no" if quiet else "steps",
        save_strategy="no",
        eval_strategy="no",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        load_best_model_at_end=False,
        dataloader_num_workers=0,
        dataloader_pin_memory=False,
        use_cpu=True,
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

    adapter_path = os.path.join(output_dir, "adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    emit(f"  Adapter saved: {adapter_path}", important=True)

    info = {
        "domain": domain,
        "model": model_name,
        "device": "cpu",
        "samples": len(texts),
        "epochs": epochs,
        "max_seq_len": max_seq_len,
        "loss": result.training_loss,
        "lora_r": 8,
        "lora_alpha": 16,
        "lora_targets": targets,
    }
    with open(os.path.join(output_dir, "training_info.json"), "w") as f:
        json.dump(info, f, indent=2)

    del model, trainer
    gc.collect()
    emit(f"\n  {domain} done!", important=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="CPU fine-tuning")
    parser.add_argument("domain", choices=DOMAINS + ["all"])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--seq-len", type=int, default=512)
    parser.add_argument(
        "--eval", action="store_true", help="Evaluate after training (ignored on CPU)"
    )
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

    # Force CPU
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    domains = DOMAINS if args.domain == "all" else [args.domain]
    for domain in domains:
        train_domain(
            domain,
            args.epochs,
            args.max_samples,
            args.seq_len,
            args.model,
            args.dataset_path,
            args.output_dir,
            args.verbose,
            args.quiet,
            args.tokenize_workers,
        )


if __name__ == "__main__":
    main()
