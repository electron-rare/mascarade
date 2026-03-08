#!/usr/bin/env python3
# ruff: noqa: E402
"""Local GPU fine-tuning script with 4-bit QLoRA.

Reads ShareGPT JSONL datasets and trains a local student model.

Usage:
  python train_local.py stm32           # Train on STM32 dataset
  python train_local.py kicad           # Train on KiCad dataset
  python train_local.py all             # Train all domains sequentially
  python train_local.py stm32 --eval    # Evaluate after training
  python train_local.py stm32 --model Qwen/Qwen2.5-Coder-7B-Instruct
"""

import argparse
import json
import os
import gc
import sys
import warnings
from itertools import chain
from importlib.util import find_spec

if "--quiet" in sys.argv:
    warnings.filterwarnings("ignore")

import transformers
from runtime_compat import disable_broken_torchvision

_RUNTIME_COMPAT_NOTE = disable_broken_torchvision()

import torch
from datasets import Dataset
from datasets.utils.logging import disable_progress_bar, enable_progress_bar
from transformers import (
    AutoConfig,
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
    "project",
]

try:
    from model_selector import resolve_model as _resolve

    DEFAULT_MODEL = _resolve("Qwen/Qwen2.5-Coder-1.5B-Instruct")
except Exception:
    DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"

# LoRA targets per model architecture
LORA_TARGETS = {
    "tinyllama": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "qwen": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "llama": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "gpt2": ["c_attn"],
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
    "mistral-small-3.1": (
        "teacher-only in this pipeline: Mistral teacher/inference model"
    ),
    "deepseek-ai/deepseek-r1": (
        "teacher-only in this pipeline: DeepSeek reasoning teacher model"
    ),
    "deepseek-ai/deepseek-v3": (
        "teacher-only in this pipeline: DeepSeek V3 teacher model"
    ),
    "deepseek-ai/deepseek-coder-v2-lite-instruct": (
        "teacher-only in this pipeline: DeepSeek coder teacher model for code-domain distillation"
    ),
}


def detect_lora_targets(model_name: str) -> list[str]:
    name = model_name.lower()
    for key, targets in LORA_TARGETS.items():
        if key in name:
            return targets
    return ["q_proj", "v_proj"]


def resolve_model_type(model_name: str) -> str | None:
    try:
        config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
    except Exception:
        return None
    return getattr(config, "model_type", None)


def assert_supported_student_model(model_name: str) -> None:
    name = model_name.lower()
    for pattern, reason in TEACHER_ONLY_STUDENT_PATTERNS.items():
        if pattern in name:
            raise ValueError(f"Unsupported student model {model_name}: {reason}")


def load_quantized_model(
    model_name: str,
    bnb_config: BitsAndBytesConfig,
    *,
    attn_implementation: str | None = None,
):
    model_type = resolve_model_type(model_name)
    common_kwargs = {
        "quantization_config": bnb_config,
        "device_map": "auto",
        "trust_remote_code": True,
    }
    if attn_implementation is not None:
        common_kwargs["attn_implementation"] = attn_implementation

    if model_type == "qwen3_5":
        try:
            from transformers import Qwen3_5ForConditionalGeneration
        except Exception as exc:
            raise RuntimeError(
                "Qwen3.5 models require a transformers build with qwen3_5 support. "
                f"Current transformers version: {transformers.__version__}"
            ) from exc
        return Qwen3_5ForConditionalGeneration.from_pretrained(
            model_name,
            **common_kwargs,
        )

    return AutoModelForCausalLM.from_pretrained(
        model_name,
        **common_kwargs,
    )


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


def supports_bf16() -> bool:
    return bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported())


def supports_tf32() -> bool:
    if not torch.cuda.is_available():
        return False
    major, _minor = torch.cuda.get_device_capability(0)
    return major >= 8


def resolve_tf32_enabled() -> bool:
    requested = os.environ.get("MASCARADE_TF32", "auto").strip().lower()
    if requested in {"0", "false", "off", "disabled"}:
        return False

    candidate = supports_tf32() if requested in {"", "auto"} else True
    if not candidate:
        return False

    # TrainingArguments performs its own runtime validation and is stricter
    # than a plain compute-capability check on some mixed/legacy CUDA setups.
    try:
        TrainingArguments(
            output_dir=os.path.join(SCRIPT_DIR, ".tf32_probe"),
            tf32=True,
            report_to="none",
        )
    except Exception:
        return False
    return True


def resolve_compute_dtype() -> torch.dtype:
    return torch.bfloat16 if supports_bf16() else torch.float16


def resolve_attention_implementation() -> str | None:
    requested = os.environ.get("MASCARADE_ATTN_IMPL", "auto").strip().lower()
    if requested in {"", "auto"}:
        if find_spec("flash_attn") is not None:
            return "flash_attention_2"
        if torch.cuda.is_available():
            return "sdpa"
        return None
    if requested in {"none", "off"}:
        return None
    return requested


def load_quantized_model_with_fallback(
    model_name: str,
    bnb_config: BitsAndBytesConfig,
    attn_implementation: str | None,
):
    try:
        return (
            load_quantized_model(
                model_name,
                bnb_config,
                attn_implementation=attn_implementation,
            ),
            attn_implementation,
        )
    except TypeError:
        if attn_implementation is None:
            raise
    except Exception as exc:
        if attn_implementation is None:
            raise
        if "flash_attention_2" not in str(exc).lower():
            raise
    model = load_quantized_model(model_name, bnb_config, attn_implementation=None)
    return model, None


def tokenize_dataset(
    dataset: Dataset,
    *,
    tokenizer,
    max_seq_len: int,
    tokenize_workers: int,
    packing: bool,
):
    def tokenize_dynamic(examples):
        return tokenizer(
            examples["text"],
            truncation=False,
            padding=False,
        )

    def tokenize_eval(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_seq_len,
            padding=False,
        )

    def group_texts(examples):
        concatenated_examples = {
            key: list(chain.from_iterable(examples[key])) for key in examples.keys()
        }
        total_length = len(concatenated_examples["input_ids"])
        if total_length < max_seq_len:
            return {key: [] for key in concatenated_examples}
        total_length = (total_length // max_seq_len) * max_seq_len
        return {
            key: [
                values[i : i + max_seq_len] for i in range(0, total_length, max_seq_len)
            ]
            for key, values in concatenated_examples.items()
        }

    map_kwargs = {
        "batched": True,
        "remove_columns": ["text"],
    }
    if tokenize_workers > 1:
        map_kwargs["num_proc"] = tokenize_workers

    train_tokenized = dataset["train"].map(tokenize_dynamic, **map_kwargs)
    eval_tokenized = dataset["test"].map(tokenize_eval, **map_kwargs)

    if not packing:
        return train_tokenized, eval_tokenized, False

    packing_kwargs = {
        "batched": True,
    }
    if tokenize_workers > 1:
        packing_kwargs["num_proc"] = tokenize_workers
    packed_train = train_tokenized.map(group_texts, **packing_kwargs)
    if len(packed_train) == 0:
        return train_tokenized, eval_tokenized, False
    return packed_train, eval_tokenized, True


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
    assert_supported_student_model(model_name)

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

    dataset = Dataset.from_dict({"text": texts})
    if len(dataset) < 2:
        raise ValueError(f"Dataset {dataset_path} needs at least 2 samples to train.")

    test_size = 1 if len(dataset) < 20 else max(1, int(len(dataset) * 0.05))
    split = dataset.train_test_split(test_size=test_size, seed=42)
    resolved_tokenize_workers = resolve_tokenize_workers(tokenize_workers, len(dataset))
    if resolved_tokenize_workers > 1:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    packing_enabled = os.environ.get(
        "MASCARADE_TRAIN_PACKING", "1"
    ).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    try:
        train_dataset, eval_dataset, used_packing = tokenize_dataset(
            split,
            tokenizer=tokenizer,
            max_seq_len=max_seq_len,
            tokenize_workers=resolved_tokenize_workers,
            packing=packing_enabled,
        )
    except Exception as exc:
        if resolved_tokenize_workers <= 1:
            raise
        emit(
            f"[WARN] tokenize workers fallback to 1 ({exc.__class__.__name__}: {exc})",
            important=True,
        )
        train_dataset, eval_dataset, used_packing = tokenize_dataset(
            split,
            tokenizer=tokenizer,
            max_seq_len=max_seq_len,
            tokenize_workers=1,
            packing=packing_enabled,
        )
        resolved_tokenize_workers = 1
    emit(
        f"  Train: {len(train_dataset)}, Test: {len(eval_dataset)}",
        important=verbose,
    )
    emit(f"  Tokenize workers: {resolved_tokenize_workers}", important=verbose)
    emit(f"  Packing: {used_packing}", important=verbose)

    # 3. Load model with 4-bit quantization
    emit("\n[3/5] Loading model (4-bit quantized)...")
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    tf32_enabled = resolve_tf32_enabled()
    torch.backends.cuda.matmul.allow_tf32 = tf32_enabled
    torch.backends.cudnn.allow_tf32 = tf32_enabled
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high" if tf32_enabled else "highest")

    compute_dtype = resolve_compute_dtype()
    attn_implementation = resolve_attention_implementation()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

    model, resolved_attn_implementation = load_quantized_model_with_fallback(
        model_name,
        bnb_config,
        attn_implementation,
    )
    model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False

    mem_mb = torch.cuda.memory_allocated() / 1024**2
    emit(f"  Model loaded: {mem_mb:.0f} MB GPU", important=verbose)
    emit(
        f"  Compute dtype: {'bf16' if compute_dtype == torch.bfloat16 else 'fp16'}",
        important=verbose,
    )
    emit(
        f"  Attention: {resolved_attn_implementation or 'default'}",
        important=verbose,
    )
    emit(f"  TF32: {'on' if tf32_enabled else 'off'}", important=verbose)

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
        fp16=compute_dtype == torch.float16,
        bf16=compute_dtype == torch.bfloat16,
        tf32=tf32_enabled,
        optim="paged_adamw_8bit",
        logging_steps=25,
        logging_strategy="no" if quiet else "steps",
        save_steps=500,
        save_total_limit=2,
        eval_strategy="steps" if len(eval_dataset) > 0 else "no",
        eval_steps=500,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        load_best_model_at_end=False,
        dataloader_pin_memory=True,
        dataloader_num_workers=max(1, min(4, resolved_tokenize_workers)),
        dataloader_persistent_workers=resolved_tokenize_workers > 1,
        disable_tqdm=quiet,
        log_level="error" if quiet else ("info" if verbose else "warning"),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
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
        "tokenize_workers": resolved_tokenize_workers,
        "packing": used_packing,
        "compute_dtype": "bf16" if compute_dtype == torch.bfloat16 else "fp16",
        "tf32": tf32_enabled,
        "attention_implementation": resolved_attn_implementation or "default",
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
