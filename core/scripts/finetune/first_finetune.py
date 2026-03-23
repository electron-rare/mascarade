#!/usr/bin/env python3
"""First fine-tune pipeline — end-to-end on the P2P mesh.

Runs locally on GrosMac, distributes training to KXKM-AI (RTX 4090).

Steps:
1. Researcher: search best small code model on HuggingFace
2. Documentalist: find matching dataset
3. Student: LoRA fine-tune on KXKM-AI via SSH
4. Save results to registry

Usage:
    python scripts/finetune/first_finetune.py
    python scripts/finetune/first_finetune.py --task code --base-model Qwen/Qwen2.5-Coder-0.5B-Instruct
"""
import asyncio
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.environ.get("PYTHONPATH", os.path.expanduser("~/mascarade/core")))

from mascarade.finetune.agents.documentalist import DocumentalistAgent
from mascarade.finetune.agents.researcher import ResearcherAgent
from mascarade.finetune.registry import FinetuneRegistry, RunEntry

# ANSI
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
RESET = "\033[0m"

HF_TOKEN = os.environ.get("HUGGINGFACE_API_KEY", "")
KXKM_SSH = "kxkm@kxkm-ai"
KXKM_VENV = "~/mascarade/core/.venv/bin/python"


def header(text: str):
    print(f"\n{BOLD}{CYAN}{'═'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*60}{RESET}\n")


def step(n: int, text: str):
    print(f"  {BOLD}{CYAN}[{n}]{RESET} {text}")


def ok(text: str):
    print(f"  {GREEN}✓{RESET} {text}")


def warn(text: str):
    print(f"  {YELLOW}⚠{RESET} {text}")


def fail(text: str):
    print(f"  {RED}✗{RESET} {text}")


def ssh_cmd(cmd: str, timeout: int = 300) -> tuple[int, str]:
    """Run command on KXKM-AI via SSH."""
    result = subprocess.run(
        ["ssh", KXKM_SSH, cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode, result.stdout + result.stderr


async def phase_research(task: str, max_size_gb: float) -> dict:
    header("PHASE 1 — RECHERCHE MODÈLES")
    researcher = ResearcherAgent(hf_token=HF_TOKEN)
    report = await researcher.recommend(task, max_size_gb=max_size_gb, top_k=5)

    for i, m in enumerate(report["candidates"], 1):
        print(f"    {i}. {CYAN}{m['model_id']}{RESET}  ↓{m['downloads']:,}  ♥{m['likes']:,}")

    if report["papers"]:
        print(f"\n    {DIM}Papers:{RESET}")
        for p in report["papers"][:3]:
            print(f"    {DIM}• {p['title'][:70]}{RESET}")

    return report


async def phase_dataset(domain: str) -> dict:
    header("PHASE 2 — RECHERCHE DATASETS")
    doc = DocumentalistAgent(hf_token=HF_TOKEN)
    report = await doc.recommend(domain, top_k=5)

    for i, d in enumerate(report["candidates"], 1):
        print(f"    {i}. {CYAN}{d['dataset_id']}{RESET}  ↓{d['downloads']:,}")

    return report


def phase_check_kxkm() -> bool:
    header("PHASE 3 — VÉRIFICATION KXKM-AI")
    step(1, "Connexion SSH...")
    rc, out = ssh_cmd("echo OK")
    if rc != 0:
        fail(f"SSH failed: {out}")
        return False
    ok("SSH OK")

    step(2, "GPU check...")
    rc, out = ssh_cmd(f"{KXKM_VENV} -c 'import torch; print(torch.cuda.get_device_name(0))'")
    if rc != 0:
        fail(f"GPU check failed: {out}")
        return False
    ok(f"GPU: {out.strip()}")

    step(3, "Packages check...")
    rc, out = ssh_cmd(f"{KXKM_VENV} -c 'import trl, peft; print(f\"trl={{trl.__version__}} peft={{peft.__version__}}\")'")
    if rc != 0:
        fail(f"Packages missing: {out}")
        return False
    ok(f"Packages: {out.strip()}")

    return True


def phase_train_remote(base_model: str, dataset_id: str, run_id: str) -> dict:
    header("PHASE 4 — TRAINING SUR KXKM-AI")

    # Create training script on KXKM
    train_script = f'''
import json, time, torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

base_model = "{base_model}"
dataset_id = "{dataset_id}"
run_id = "{run_id}"
output_dir = f"/tmp/mascarade-ft/{{run_id}}"

print(f"Loading model: {{base_model}}")
start = time.time()

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

tokenizer = AutoTokenizer.from_pretrained(base_model)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    base_model,
    quantization_config=bnb_config,
    device_map="auto",
    torch_dtype=torch.bfloat16,
)

print(f"Loading dataset: {{dataset_id}}")
try:
    dataset = load_dataset(dataset_id, split="train[:500]")
except Exception:
    dataset = load_dataset(dataset_id, split="train")
    if len(dataset) > 500:
        dataset = dataset.select(range(500))

# Find text column
text_col = None
for col in ["text", "content", "instruction", "input", "prompt", "code"]:
    if col in dataset.column_names:
        text_col = col
        break
if text_col is None:
    text_col = dataset.column_names[0]

def format_dataset(example):
    return {{"text": str(example[text_col])[:2048]}}

dataset = dataset.map(format_dataset)

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"],
    task_type="CAUSAL_LM",
)

training_args = SFTConfig(
    output_dir=output_dir,
    num_train_epochs=1,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    bf16=True,
    logging_steps=5,
    save_strategy="no",
    report_to="none",
    max_steps=50,
    max_length=512,
    dataset_text_field="text",
)

print("Starting training...")
trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    peft_config=lora_config,
    processing_class=tokenizer,
)

trainer.train()
elapsed = time.time() - start
logs = trainer.state.log_history
final_loss = logs[-1].get("train_loss", logs[-1].get("loss", 0.0)) if logs else 0.0

trainer.save_model(f"{{output_dir}}/adapter")
tokenizer.save_pretrained(f"{{output_dir}}/adapter")

result = {{
    "run_id": run_id,
    "base_model": base_model,
    "dataset": dataset_id,
    "method": "qlora-4bit",
    "training_time_seconds": round(elapsed, 1),
    "final_loss": round(final_loss, 4),
    "max_steps": 50,
    "output_dir": output_dir,
    "status": "completed",
}}
print("RESULT_JSON:" + json.dumps(result))
'''

    # Write script to KXKM
    step(1, "Deploying training script to KXKM-AI...")
    script_path = "/tmp/mascarade_train.py"
    # Write via stdin
    proc = subprocess.run(
        ["ssh", KXKM_SSH, f"cat > {script_path}"],
        input=train_script, text=True, timeout=10,
    )
    if proc.returncode != 0:
        fail("Failed to deploy script")
        return {"status": "failed", "error": "deploy failed"}
    ok("Script deployed")

    step(2, f"Training {base_model} on {dataset_id}...")
    print(f"    {DIM}(QLoRA 4bit, 50 steps, batch=2, lr=2e-4){RESET}")
    print(f"    {DIM}This may take a few minutes...{RESET}\n")

    try:
        result = subprocess.run(
            ["ssh", KXKM_SSH, f"{KXKM_VENV} {script_path}"],
            capture_output=True, text=True, timeout=1800,
        )

        # Print training output
        for line in result.stdout.split("\n"):
            if line.strip():
                if "RESULT_JSON:" in line:
                    continue
                print(f"    {DIM}{line}{RESET}")

        # Extract result
        for line in result.stdout.split("\n"):
            if "RESULT_JSON:" in line:
                try:
                    data = json.loads(line.split("RESULT_JSON:")[1])
                except json.JSONDecodeError as e:
                    fail(f"Failed to parse training result: {e}")
                    return {"status": "failed", "error": f"JSON parse error: {e}"}
                ok(f"Training complete in {data['training_time_seconds']}s, loss={data['final_loss']}")
                return data

        if result.returncode != 0:
            fail("Training failed")
            for line in result.stderr.split("\n")[-10:]:
                if line.strip():
                    print(f"    {RED}{line}{RESET}")
            return {"status": "failed", "error": result.stderr[-500:]}

    except subprocess.TimeoutExpired:
        fail("Training timed out (30min)")
        return {"status": "failed", "error": "timeout"}

    return {"status": "failed", "error": "no result found"}


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="First fine-tune pipeline")
    parser.add_argument("--task", default="code", help="Model task")
    parser.add_argument("--domain", default="code", help="Dataset domain")
    parser.add_argument("--max-size", type=float, default=3.0, help="Max model size GB")
    parser.add_argument("--base-model", default="", help="Override base model (skip research)")
    parser.add_argument("--dataset", default="", help="Override dataset (skip research)")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual training")
    args = parser.parse_args()

    header("MASCARADE FIRST FINE-TUNE")
    print(f"  Task: {args.task}")
    print(f"  Domain: {args.domain}")
    print(f"  Max size: {args.max_size}GB")
    print("  Training node: KXKM-AI (RTX 4090)")

    registry = FinetuneRegistry()
    run_id = f"ft-{args.task}-{int(time.time())}"

    # Phase 1: Research (or use override)
    if args.base_model:
        selected_model = args.base_model
        ok(f"Using specified model: {selected_model}")
    else:
        model_report = await phase_research(args.task, args.max_size)
        if not model_report["candidates"]:
            fail("No model candidates found")
            return
        selected_model = model_report["candidates"][0]["model_id"]
        ok(f"Selected: {selected_model}")

    # Phase 2: Dataset (or use override)
    if args.dataset:
        selected_dataset = args.dataset
        ok(f"Using specified dataset: {selected_dataset}")
    else:
        ds_report = await phase_dataset(args.domain)
        if not ds_report["candidates"]:
            fail("No dataset candidates found")
            return
        selected_dataset = ds_report["candidates"][0]["dataset_id"]
        ok(f"Selected: {selected_dataset}")

    # Phase 3: Check KXKM
    if not phase_check_kxkm():
        fail("KXKM-AI not ready")
        return

    if args.dry_run:
        header("DRY RUN — skipping training")
        ok(f"Would train {selected_model} on {selected_dataset}")
        return

    # Phase 4: Train
    result = phase_train_remote(selected_model, selected_dataset, run_id)

    # Phase 5: Save to registry
    header("PHASE 5 — SAUVEGARDE REGISTRE")
    registry.add_run(RunEntry(
        run_id=run_id,
        base_model=selected_model,
        dataset=selected_dataset,
        method=result.get("method", "qlora-4bit"),
        node="KXKM-AI",
        status=result.get("status", "failed"),
        metrics={
            "final_loss": result.get("final_loss", 0),
            "training_time": result.get("training_time_seconds", 0),
            "max_steps": result.get("max_steps", 0),
        },
    ))
    ok(f"Run {run_id} saved to registry")

    # Summary
    header("RÉSULTAT")
    status_color = GREEN if result.get("status") == "completed" else RED
    print(f"  Status: {status_color}{result.get('status', 'unknown')}{RESET}")
    print(f"  Model: {selected_model}")
    print(f"  Dataset: {selected_dataset}")
    print(f"  Method: {result.get('method', '-')}")
    print(f"  Loss: {result.get('final_loss', '-')}")
    print(f"  Time: {result.get('training_time_seconds', '-')}s")
    print(f"  Output: {result.get('output_dir', '-')}")
    print(f"  Run ID: {run_id}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
