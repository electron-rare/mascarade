"""Train all mini-models from their domain-specific datasets.

Each mini-model = 1 small finetune (~30min-2h) on its domain data.
The mascarade router dispatches to the right mini-model per query."""

import json
import time
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["WANDB_DISABLED"] = "true"

BASE = "finetune/datasets"
RUNS = "finetune/runs"
BASE_MODEL = "unsloth/Qwen3-8B-unsloth-bnb-4bit"

# Mini-model definitions: name -> list of dataset files
MINI_MODELS = {
    "mascarade-kicad-v3": {
        "datasets": [
            f"{BASE}/kicad_chat_v3_multi.jsonl",
            f"{BASE}/kicad10_features_cleaned.jsonl",
            f"{BASE}/hf_imports/open_schematics.jsonl",
        ],
        "epochs": 2,
        "system": "You are an expert KiCad PCB designer.",
    },
    "mascarade-spice-v2": {
        "datasets": [f"{BASE}/spice_chat.jsonl"],
        "epochs": 3,
        "system": "You are an expert SPICE simulation engineer.",
    },
    "mascarade-analog-audio": {
        "datasets": [f"{BASE}/analog_audio_electronics_cleaned.jsonl"],
        "epochs": 3,
        "system": "You are an expert analog and audio electronics engineer.",
    },
    "mascarade-embedded-v2": {
        "datasets": [
            f"{BASE}/embedded_systems_full_cleaned.jsonl",
            f"{BASE}/platformio_chat.jsonl",
            f"{BASE}/stm32_chat.jsonl",
        ],
        "epochs": 2,
        "system": "You are an expert embedded systems firmware engineer.",
    },
    "mascarade-ipc-standards": {
        "datasets": [
            f"{BASE}/ipc_jlcpcb_standards_cleaned.jsonl",
            f"{BASE}/emc_chat.jsonl",
        ],
        "epochs": 3,
        "system": "You are an expert in IPC standards, EMC, and PCB manufacturing.",
    },
    "mascarade-power-v2": {
        "datasets": [f"{BASE}/power_chat.jsonl"],
        "epochs": 3,
        "system": "You are an expert power electronics engineer.",
    },
    "mascarade-dsp-v2": {
        "datasets": [f"{BASE}/dsp_chat.jsonl"],
        "epochs": 3,
        "system": "You are an expert DSP engineer.",
    },
    "mascarade-rf-wireless": {
        "datasets": [f"{BASE}/missing_domains_cleaned.jsonl"],
        "filter_domain": "rf-and-wireless-design",
        "epochs": 3,
        "system": "You are an expert RF and wireless design engineer.",
    },
    "mascarade-verilog-v2": {
        "datasets": [
            f"{BASE}/hf_imports/rtlcoder3.jsonl",
            f"{BASE}/hf_imports/verireason_rtlcoder_reasoning.jsonl",
            f"{BASE}/hf_imports/verireason_combined.jsonl",
            f"{BASE}/hf_imports/mg_verilog.jsonl",
            f"{BASE}/hf_imports/verilogos_augmented.jsonl",
        ],
        "epochs": 1,
        "system": "You are an expert Verilog/SystemVerilog RTL designer.",
    },
}


def load_and_merge_datasets(config):
    """Load and merge datasets for a mini-model."""
    from datasets import load_dataset, concatenate_datasets

    all_ds = []
    for path in config["datasets"]:
        if not os.path.exists(path):
            print(f"  SKIP {os.path.basename(path)} (not found)")
            continue
        try:
            ds = load_dataset("json", data_files=path, split="train")
            # Filter by domain if specified
            if "filter_domain" in config:
                ds = ds.filter(lambda x: x.get("domain", "") == config["filter_domain"])
            all_ds.append(ds)
            print(f"  + {os.path.basename(path)}: {len(ds)} examples")
        except Exception as e:
            print(f"  ERROR {path}: {e}")

    if not all_ds:
        return None

    merged = concatenate_datasets(all_ds) if len(all_ds) > 1 else all_ds[0]
    return merged


def format_for_training(dataset):
    """Convert conversations format to text for SFT."""
    def format_chat(example):
        convs = example.get("conversations", [])
        text = ""
        for msg in convs:
            role = msg.get("from", msg.get("role", ""))
            content = msg.get("value", msg.get("content", ""))
            if not content:
                continue
            if role in ("system", "human", "user"):
                text += f"<s>[INST] {content} [/INST]"
            elif role in ("assistant", "gpt"):
                text += f" {content}</s>"

        # Fallback for instruction/output format
        if not text:
            inst = example.get("instruction", "")
            out = example.get("output", "")
            if inst and out:
                text = f"<s>[INST] {inst} [/INST] {out}</s>"

        return {"text": text}

    dataset = dataset.map(format_chat)
    dataset = dataset.filter(lambda x: len(x.get("text", "")) > 50)
    return dataset


def train_mini_model(name, config):
    """Train one mini-model."""
    from unsloth import FastLanguageModel
    from trl import SFTTrainer, SFTConfig

    run_dir = f"{RUNS}/{name}-{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(run_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Training: {name}")
    print(f"{'='*60}")

    # Load datasets
    dataset = load_and_merge_datasets(config)
    if dataset is None or len(dataset) < 10:
        print("  SKIP — not enough data")
        return None

    # Format
    dataset = format_for_training(dataset)
    print(f"  Total: {len(dataset)} examples after formatting")

    # Cap at 10K for mini-models (more would take too long)
    if len(dataset) > 10000:
        dataset = dataset.shuffle(seed=42).select(range(10000))
        print("  Capped to 10000 examples")

    # Load model
    print(f"  Loading {BASE_MODEL}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=2048,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        random_state=42,
    )

    # Train
    training_args = SFTConfig(
        output_dir=run_dir,
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        warmup_steps=50,
        logging_steps=25,
        save_steps=500,
        max_seq_length=2048,
        dataset_text_field="text",
        bf16=True,
        seed=42,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )

    start = time.time()
    trainer.train()
    duration = time.time() - start

    # Save
    model.save_pretrained(f"{run_dir}/lora")
    tokenizer.save_pretrained(f"{run_dir}/lora")

    manifest = {
        "name": name,
        "base_model": BASE_MODEL,
        "datasets": config["datasets"],
        "examples": len(dataset),
        "epochs": config["epochs"],
        "duration_seconds": duration,
        "output_dir": run_dir,
    }
    with open(f"{run_dir}/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  DONE in {duration:.0f}s — {run_dir}")
    return run_dir


def main():
    print("=== Mini-Model Training Pipeline ===")
    print(f"Base model: {BASE_MODEL}")
    print(f"Models to train: {len(MINI_MODELS)}\n")

    results = {}
    for name, config in MINI_MODELS.items():
        # Check if enough data exists
        has_data = any(os.path.exists(p) for p in config["datasets"])
        if not has_data:
            print(f"\nSKIP {name} — no datasets found")
            continue

        try:
            run_dir = train_mini_model(name, config)
            results[name] = {"status": "done", "run_dir": run_dir}
        except Exception as e:
            print(f"  FAILED: {e}")
            results[name] = {"status": "failed", "error": str(e)}

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    for name, r in results.items():
        print(f"  {name}: {r['status']}")

    with open(f"{RUNS}/mini-models-results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
