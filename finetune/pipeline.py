#!/usr/bin/env python3
# ruff: noqa: E402
"""
Mascarade Local Fine-Tuning Pipeline
=====================================
Full pipeline: fine-tune → merge → GGUF export → Ollama deploy.

Takes a recent base model (Qwen2.5-Coder-7B, Qwen3-8B, etc.),
fine-tunes it with QLoRA on domain-specific datasets, then exports
a small quantized GGUF model ready for Ollama.

Hardware: Quadro P2000 (5GB VRAM) + 31GB RAM
Strategy: 4-bit QLoRA on GPU, optimizer states offloaded to CPU RAM.

Usage:
  # Full pipeline for one domain
  python pipeline.py stm32

  # Use a different base model
  python pipeline.py kicad --base Qwen/Qwen2.5-Coder-7B-Instruct

  # All domains sequentially
  python pipeline.py all

  # Steps individually
  python pipeline.py stm32 --step train
  python pipeline.py stm32 --step merge
  python pipeline.py stm32 --step gguf
  python pipeline.py stm32 --step deploy
"""

import argparse
import json
import os
import gc
import subprocess
import sys
from pathlib import Path

# Ensure sibling modules are importable when loaded via spec_from_file_location.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from dataset_quality import (
    DatasetQualityError,
    enforce_dataset_quality,
    summarize_quality_report,
)
from llm_paths import configure_hf_env, hf_cache_roots, shared_model_cache_dir
from runtime_compat import disable_broken_torchvision
from sharegpt_utils import ensure_row_ids_with_stats, load_jsonl, validate_rows

try:
    from .ollama_runtime import (
        OllamaRuntimeError,
        create_model,
        resolve_ollama_runtime,
        run_model,
    )
except ImportError:  # pragma: no cover - script execution path
    from ollama_runtime import (
        OllamaRuntimeError,
        create_model,
        resolve_ollama_runtime,
        run_model,
    )

_RUNTIME_COMPAT_NOTE = disable_broken_torchvision()

configure_hf_env()

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
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent.resolve()
DATASETS_DIR = SCRIPT_DIR / "datasets"
MODELS_DIR = Path(
    os.environ.get("MASCARADE_FINETUNE_MODELS_DIR", str(SCRIPT_DIR / "models_local"))
).resolve()
MODELFILES_DIR = SCRIPT_DIR / "modelfiles"

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

LOCAL_SHARED_MODEL_CACHE = shared_model_cache_dir()
LOCAL_QWEN25_7B = LOCAL_SHARED_MODEL_CACHE / "qwen2.5-7b"

# Base models ranked by quality (pick first that fits in VRAM)
# Local cache paths take priority
BASE_MODELS = {
    "qwen2.5-coder-7b": (
        str(LOCAL_QWEN25_7B)
        if LOCAL_QWEN25_7B.exists()
        else "Qwen/Qwen2.5-Coder-7B-Instruct"
    ),
    "qwen3-8b": "Qwen/Qwen3-8B",
    "qwen3-1.7b": "Qwen/Qwen3-1.7B",
    "deepseek-coder": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
    "tinyllama": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
}

DEFAULT_BASE = BASE_MODELS["qwen2.5-coder-7b"]
GGUF_QUANTS = ["q4_k_m", "q4_k_s", "q5_k_m", "q8_0"]
TRAIN_QUANT_MODES = ["4bit", "none"]

# Chat templates per model family
CHAT_TEMPLATES = {
    "qwen": {
        "system": "<|im_start|>system\n{}<|im_end|>",
        "user": "<|im_start|>user\n{}<|im_end|>",
        "asst": "<|im_start|>assistant\n{}<|im_end|>",
    },
    "tinyllama": {
        "system": "<|system|>\n{}</s>",
        "user": "<|user|>\n{}</s>",
        "asst": "<|assistant|>\n{}</s>",
    },
    "deepseek": {
        "system": "<|begin▁of▁sentence|>{}\n",
        "user": "User: {}\n",
        "asst": "Assistant: {}<|end▁of▁sentence|>",
    },
}


def resolve_local_hf_model_path(model_name: str) -> str:
    suffix = f"models--{model_name.replace('/', '--')}"
    for root in hf_cache_roots():
        snapshots_dir = root / suffix / "snapshots"
        if not snapshots_dir.exists():
            continue
        snapshots = sorted(
            (path for path in snapshots_dir.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for snapshot in snapshots:
            if (snapshot / "config.json").exists():
                return str(snapshot.resolve())
    return model_name


def resolve_model_source(model_ref: str) -> str:
    """Resolve a local model path to an absolute filesystem path when possible."""
    candidate = Path(model_ref)
    search_paths = []
    if candidate.is_absolute():
        search_paths.append(candidate)
    else:
        search_paths.extend(
            [
                candidate,
                REPO_ROOT / candidate,
                SCRIPT_DIR / candidate,
            ]
        )
    for path in search_paths:
        if path.exists():
            return str(path.resolve())
    return resolve_local_hf_model_path(model_ref)


def detect_family(model_name: str) -> str:
    name = model_name.lower()
    if "qwen" in name:
        return "qwen"
    if "deepseek" in name:
        return "deepseek"
    if "tinyllama" in name:
        return "tinyllama"
    return "qwen"  # default


def format_conversation(convos: list[dict], family: str) -> str:
    tpl = CHAT_TEMPLATES.get(family, CHAT_TEMPLATES["qwen"])
    parts = []
    for msg in convos:
        role = msg["from"]
        val = msg["value"]
        if role == "system":
            parts.append(tpl["system"].format(val))
        elif role == "human":
            parts.append(tpl["user"].format(val))
        elif role == "gpt":
            parts.append(tpl["asst"].format(val))
    return "\n".join(parts)


def load_dataset_jsonl(
    path: str, family: str, max_samples: int | None = None
) -> list[str]:
    texts = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break
            row = json.loads(line)
            text = format_conversation(row.get("conversations", []), family)
            if text:
                texts.append(text)
    return texts


# ──────────────────────────────────────────────────────────────
# STEP 1: Train
# ──────────────────────────────────────────────────────────────
def step_train(
    domain: str,
    base_model: str,
    epochs: int = 3,
    max_seq_len: int = 512,
    max_samples: int | None = None,
    train_quant: str = "4bit",
):
    base_model = resolve_model_source(base_model)
    dataset_path = DATASETS_DIR / f"{domain}_chat.jsonl"
    if not dataset_path.exists():
        print(f"[!] Dataset not found: {dataset_path}")
        return False
    raw_rows = load_jsonl(dataset_path)
    normalized_rows, normalized_source_ids = ensure_row_ids_with_stats(
        raw_rows, f"{domain}-dataset"
    )
    validation_errors = validate_rows(normalized_rows)
    if validation_errors:
        for error in validation_errors[:10]:
            print(f"[ERROR] {error}")
        print(f"[!] Dataset is invalid ({len(validation_errors)} errors)")
        return False
    try:
        dataset_quality = enforce_dataset_quality(
            normalized_rows,
            label=f"{domain} dataset",
            ids_fixed=normalized_source_ids,
        )
    except DatasetQualityError as exc:
        print(f"[!] Dataset quality gate failed: {exc}")
        return False

    output_dir = MODELS_DIR / domain
    output_dir.mkdir(parents=True, exist_ok=True)

    family = detect_family(base_model)

    print(f"\n{'='*60}")
    print(f"  TRAIN: {domain}")
    print(f"  Base:  {base_model}")
    print(f"  Chat:  {family}")
    print(f"  Seq:   {max_seq_len}, Epochs: {epochs}")
    print(f"{'='*60}")
    if dataset_quality["warnings"]:
        print(f"  [WARN] quality: {summarize_quality_report(dataset_quality)}")

    gc.collect()
    torch.cuda.empty_cache()

    # Load dataset
    print("\n[1/5] Dataset...")
    texts = load_dataset_jsonl(str(dataset_path), family, max_samples)
    print(f"  {len(texts)} examples")

    # Tokenizer
    print("\n[2/5] Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        trust_remote_code=True,
        local_files_only=Path(base_model).exists(),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    def tokenize(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_seq_len,
            padding="max_length",
        )

    ds = Dataset.from_dict({"text": texts})
    split = ds.train_test_split(test_size=min(100, max(10, len(texts) // 20)), seed=42)
    tok_ds = split.map(tokenize, batched=True, remove_columns=["text"])
    print(f"  Train: {len(tok_ds['train'])}, Eval: {len(tok_ds['test'])}")

    # Model
    if train_quant == "none":
        print("\n[3/5] Model (FP16 sans quantification)...")
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        model_kwargs = {
            "device_map": "auto",
            "trust_remote_code": True,
            "torch_dtype": torch.float16,
        }
        optimizer = "adamw_torch"
    else:
        print("\n[3/5] Model (4-bit NF4 avec offloading CPU)...")
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        device_map = {
            "": "cuda:0",
            "model.embed_tokens": "cpu",
            "model.norm": "cpu",
            "lm_head": "cpu",
        }
        model_kwargs = {
            "quantization_config": bnb_config,
            "device_map": device_map,
            "trust_remote_code": True,
            "torch_dtype": torch.float16,
        }
        optimizer = "paged_adamw_8bit"

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        **model_kwargs,
        local_files_only=Path(base_model).exists(),
    )
    if train_quant != "none":
        model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    vram = torch.cuda.memory_allocated() / 1024**2
    print(f"  Loaded: {vram:.0f} MB VRAM")

    # LoRA
    print("\n[4/5] LoRA...")
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
    try:
        model = get_peft_model(model, lora_config)
    except ValueError:
        # Fallback for models without gate/up/down proj
        lora_config.target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]
        model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Train
    print("\n[5/5] Training...")
    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        fp16=True,
        optim=optimizer,
        logging_steps=10,
        save_steps=200,
        save_total_limit=2,
        eval_strategy="steps",
        eval_steps=200,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        load_best_model_at_end=False,
        dataloader_pin_memory=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tok_ds["train"],
        eval_dataset=tok_ds["test"],
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    result = trainer.train()
    loss = result.training_loss
    print(f"\n  Loss: {loss:.4f}")

    # Save adapter
    adapter_path = output_dir / "adapter"
    model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))

    # Save metadata
    meta = {
        "domain": domain,
        "base_model": base_model,
        "family": family,
        "samples": len(texts),
        "epochs": epochs,
        "seq_len": max_seq_len,
        "loss": loss,
        "train_quant": train_quant,
        "lora_r": 16,
        "lora_alpha": 32,
    }
    (output_dir / "training_info.json").write_text(json.dumps(meta, indent=2))
    print(f"  Adapter saved: {adapter_path}")

    del model, trainer
    gc.collect()
    torch.cuda.empty_cache()
    return True


# ──────────────────────────────────────────────────────────────
# STEP 2: Merge adapter into base model (full FP16 on CPU)
# ──────────────────────────────────────────────────────────────
def step_merge(domain: str, base_model: str | None = None):
    output_dir = MODELS_DIR / domain
    adapter_path = output_dir / "adapter"
    merged_path = output_dir / "merged"

    if not adapter_path.exists():
        print(f"[!] No adapter at {adapter_path} — run train first")
        return False

    # Read base model from training info
    if base_model is None:
        info = json.loads((output_dir / "training_info.json").read_text())
        base_model = info.get("base_model") or info.get("model")
    base_model = resolve_model_source(base_model)

    print(f"\n{'='*60}")
    print(f"  MERGE: {domain}")
    print(f"  Base:  {base_model}")
    print(f"  Into:  {merged_path}")
    print(f"{'='*60}")

    # Load base model in FP16 on CPU (needs ~14GB RAM for 7B)
    print("\n  Loading base model on CPU (FP16)...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="cpu",
        trust_remote_code=True,
        local_files_only=Path(base_model).exists(),
    )

    # Load and merge adapter
    print("  Loading adapter...")
    model = PeftModel.from_pretrained(model, str(adapter_path))
    print("  Merging weights...")
    model = model.merge_and_unload()

    # Save
    print(f"  Saving merged model to {merged_path}...")
    merged_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(merged_path), safe_serialization=True)

    tokenizer = AutoTokenizer.from_pretrained(str(adapter_path), local_files_only=True)
    tokenizer.save_pretrained(str(merged_path))

    size_gb = (
        sum(f.stat().st_size for f in merged_path.rglob("*") if f.is_file()) / 1024**3
    )
    print(f"  Merged model size: {size_gb:.1f} GB")

    del model
    gc.collect()
    return True


# ──────────────────────────────────────────────────────────────
# STEP 3: Convert to GGUF
# ──────────────────────────────────────────────────────────────
def step_gguf(domain: str, quant: str = "q4_k_m"):
    output_dir = MODELS_DIR / domain
    merged_path = output_dir / "merged"
    gguf_path = output_dir / f"mascarade-{domain}-{quant}.gguf"

    if not merged_path.exists():
        print(f"[!] No merged model at {merged_path} — run merge first")
        return False

    print(f"\n{'='*60}")
    print(f"  GGUF EXPORT: {domain}")
    print(f"  Quant: {quant}")
    print(f"  Output: {gguf_path}")
    print(f"{'='*60}")

    # Find llama.cpp convert script
    # Try multiple locations
    convert_script = None
    for candidate in [
        SCRIPT_DIR / "llama.cpp" / "convert_hf_to_gguf.py",
        Path.home() / "llama.cpp" / "convert_hf_to_gguf.py",
        Path("/usr/local/bin/convert_hf_to_gguf.py"),
    ]:
        if candidate.exists():
            convert_script = candidate
            break

    if convert_script is None:
        # Clone llama.cpp if not available
        llama_dir = SCRIPT_DIR / "llama.cpp"
        print("  llama.cpp not found, cloning...")
        subprocess.run(
            [
                "git",
                "clone",
                "--depth=1",
                "https://github.com/ggml-org/llama.cpp.git",
                str(llama_dir),
            ],
            check=True,
        )
        convert_script = llama_dir / "convert_hf_to_gguf.py"
        # Install requirements
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(llama_dir / "requirements.txt"),
            ],
            check=False,
        )

    # Step 1: Convert to FP16 GGUF
    fp16_gguf = output_dir / f"mascarade-{domain}-f16.gguf"
    print("\n  Converting to FP16 GGUF...")
    subprocess.run(
        [
            sys.executable,
            str(convert_script),
            str(merged_path),
            "--outfile",
            str(fp16_gguf),
            "--outtype",
            "f16",
        ],
        check=True,
    )

    # Step 2: Quantize
    # Find llama-quantize binary
    quantize_bin = None
    for candidate in [
        SCRIPT_DIR / "llama.cpp" / "build" / "bin" / "llama-quantize",
        SCRIPT_DIR / "llama.cpp" / "llama-quantize",
        Path("/usr/local/bin/llama-quantize"),
    ]:
        if candidate.exists():
            quantize_bin = candidate
            break

    if quantize_bin is None:
        # Build llama.cpp
        llama_dir = SCRIPT_DIR / "llama.cpp"
        print("\n  Building llama.cpp (cmake)...")
        build_dir = llama_dir / "build"
        build_dir.mkdir(exist_ok=True)
        subprocess.run(
            ["cmake", "..", "-DCMAKE_BUILD_TYPE=Release"],
            cwd=str(build_dir),
            check=True,
        )
        subprocess.run(
            ["cmake", "--build", ".", "--config", "Release", "-j4"],
            cwd=str(build_dir),
            check=True,
        )
        quantize_bin = build_dir / "bin" / "llama-quantize"

    print(f"\n  Quantizing to {quant}...")
    subprocess.run(
        [str(quantize_bin), str(fp16_gguf), str(gguf_path), quant.upper()],
        check=True,
    )

    # Cleanup FP16 intermediate
    fp16_gguf.unlink(missing_ok=True)

    size_gb = gguf_path.stat().st_size / 1024**3
    print(f"\n  GGUF ready: {gguf_path} ({size_gb:.1f} GB)")
    return True


# ──────────────────────────────────────────────────────────────
# STEP 4: Deploy to Ollama
# ──────────────────────────────────────────────────────────────
def step_deploy(domain: str, deploy_alias: str | None = None):
    output_dir = MODELS_DIR / domain
    gguf_files = list(output_dir.glob("*.gguf"))
    if not gguf_files:
        print(f"[!] No GGUF file in {output_dir} — run gguf step first")
        return False

    gguf_path = gguf_files[0]
    model_name = (deploy_alias or f"mascarade-{domain}").strip()

    # Use existing Modelfile or generate one
    modelfile_src = MODELFILES_DIR / f"Modelfile.{domain}"
    if not modelfile_src.exists():
        print(f"  No Modelfile for {domain}, generating default...")
        modelfile_src = output_dir / "Modelfile"
        modelfile_src.write_text(
            f"FROM ./model.gguf\n"
            f"PARAMETER temperature 0.3\n"
            f"PARAMETER top_p 0.9\n"
            f"PARAMETER num_ctx 2048\n"
            f'SYSTEM "You are an expert {domain} engineer. '
            f'Provide detailed, production-ready technical answers with code examples."\n'
        )

    print(f"\n{'='*60}")
    print(f"  DEPLOY: {model_name}")
    print(f"  GGUF:   {gguf_path}")
    print(f"{'='*60}")

    # Create temp Modelfile with correct GGUF path
    tmp_modelfile = output_dir / "Modelfile.deploy"
    content = modelfile_src.read_text()
    content = content.replace("FROM ./model.gguf", f"FROM {gguf_path}")
    # If FROM line doesn't reference model.gguf, replace first FROM line
    if str(gguf_path) not in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("FROM"):
                lines[i] = f"FROM {gguf_path}"
                break
        content = "\n".join(lines)
    tmp_modelfile.write_text(content)

    try:
        runtime = resolve_ollama_runtime()
    except OllamaRuntimeError as exc:
        print(f"  [!] Unable to resolve an Ollama deploy target: {exc}")
        tmp_modelfile.unlink(missing_ok=True)
        return False

    print(f"\n  Ollama runtime: {runtime['mode']} ({runtime['reason']})")
    print(f"  Creating Ollama model '{model_name}'...")
    result = create_model(
        runtime,
        model_name=model_name,
        modelfile_path=tmp_modelfile,
        gguf_path=gguf_path,
    )
    if result.returncode != 0:
        print(f"  [!] ollama create failed: {result.stderr or result.stdout}")
        tmp_modelfile.unlink(missing_ok=True)
        return False

    print("  Model created!")

    # Quick test
    print("\n  Testing...")
    test_prompts = {
        "stm32": "Write a simple GPIO toggle on STM32F4",
        "kicad": "How to set DRC rules in KiCad for JLCPCB?",
        "spice": "Write a SPICE netlist for a voltage divider",
        "iot": "Write MQTT publish code for ESP32",
        "power": "Calculate inductor for a buck converter 12V to 5V 2A",
        "dsp": "Implement a moving average filter in C",
        "emc": "Decoupling capacitor values for 100MHz IC?",
        "embedded": "Write bare-metal SysTick timer init for Cortex-M4",
        "platformio": "Write a minimal PlatformIO pio.ini for ESP32 with OTA enabled",
        "freecad": "Write a short FreeCAD Python macro for a parametric enclosure box",
        "components": "Suggest two good alternatives to LM317 and explain when each is better",
    }
    prompt = test_prompts.get(domain, "Hello, describe your specialty.")
    result = run_model(runtime, model_name=model_name, prompt=prompt, timeout=120)
    if result.returncode == 0:
        print("  Response (first 300 chars):")
        print(f"  {result.stdout[:300]}")
    else:
        print(f"  Test failed: {result.stderr[:200]}")

    # Cleanup
    tmp_modelfile.unlink(missing_ok=True)

    print(f"\n  Deployed! Use: ollama run {model_name}")
    print(f"  In Mascarade: provider='ollama', model='{model_name}'")
    return True


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def run_pipeline(domain: str, base_model: str, step: str | None, **kwargs):
    steps = ["train", "merge", "gguf", "deploy"] if step is None else [step]
    train_quant = kwargs.get("train_quant", "4bit")
    gguf_quant = kwargs.get("quant", "q4_k_m")

    for s in steps:
        print(f"\n{'#'*60}")
        print(f"# PIPELINE STEP: {s.upper()} — {domain}")
        print(f"{'#'*60}")

        if s == "train":
            ok = step_train(
                domain,
                base_model,
                epochs=kwargs.get("epochs", 3),
                max_seq_len=kwargs.get("seq_len", 512),
                max_samples=kwargs.get("max_samples"),
                train_quant=train_quant,
            )
        elif s == "merge":
            ok = step_merge(domain, base_model)
        elif s == "gguf":
            ok = step_gguf(domain, gguf_quant)
        elif s == "deploy":
            ok = step_deploy(domain, deploy_alias=kwargs.get("deploy_alias"))
        else:
            print(f"[!] Unknown step: {s}")
            ok = False

        if not ok:
            print(f"\n[!] Step {s} failed for {domain}, stopping.")
            return False

    print(f"\n{'='*60}")
    print(f"  Pipeline complete for {domain}!")
    print(f"{'='*60}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Mascarade local fine-tuning pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py stm32                         # Full pipeline
  python pipeline.py kicad --base Qwen/Qwen3-8B    # Use Qwen3
  python pipeline.py all                            # All domains
  python pipeline.py stm32 --step train             # Train only
  python pipeline.py stm32 --step merge             # Merge only
  python pipeline.py stm32 --step gguf              # GGUF export
  python pipeline.py stm32 --step deploy            # Deploy to Ollama

Available base models:
  Qwen/Qwen2.5-Coder-7B-Instruct  (default, best for code)
  Qwen/Qwen3-8B                    (newest, polyvalent)
  Qwen/Qwen3-1.7B                  (tiny, fast)
  TinyLlama/TinyLlama-1.1B-Chat-v1.0
        """,
    )
    parser.add_argument("domain", choices=DOMAINS + ["all"])
    parser.add_argument("--base", default=DEFAULT_BASE, help="Base model")
    parser.add_argument(
        "--step",
        choices=["train", "merge", "gguf", "deploy"],
        default=None,
        help="Run single step",
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--seq-len", type=int, default=512)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument(
        "--quant",
        default="q4_k_m",
        choices=GGUF_QUANTS + ["none"],
        help="GGUF quantization format; `none` is kept only as a legacy alias for FP16 training load",
    )
    parser.add_argument(
        "--train-quant",
        default=None,
        choices=TRAIN_QUANT_MODES,
        help="Training load mode: `4bit` for QLoRA, `none` for full FP16 load",
    )
    parser.add_argument(
        "--deploy-alias",
        default=None,
        help="Override the Ollama model alias used during the deploy step",
    )
    args = parser.parse_args()
    train_quant = args.train_quant or "4bit"
    gguf_quant = args.quant

    if args.quant == "none":
        if args.train_quant is None:
            train_quant = "none"
        gguf_quant = "q4_k_m"
        print(
            "[!] `--quant none` est interprete comme un alias legacy pour "
            "`--train-quant none --quant q4_k_m`."
        )

    domains = DOMAINS if args.domain == "all" else [args.domain]

    for domain in domains:
        extra_kwargs: dict[str, object] = {}
        if args.deploy_alias is not None:
            extra_kwargs["deploy_alias"] = args.deploy_alias
        run_pipeline(
            domain,
            args.base,
            args.step,
            epochs=args.epochs,
            seq_len=args.seq_len,
            max_samples=args.max_samples,
            quant=gguf_quant,
            train_quant=train_quant,
            **extra_kwargs,
        )


if __name__ == "__main__":
    main()
