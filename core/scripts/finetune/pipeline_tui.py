#!/usr/bin/env python3
"""Fine-tuning Pipeline TUI — full orchestration with live logs.

Interactive pipeline: Research → Dataset → Teacher → Training → Eval → Validation
Runs locally, distributes training to KXKM-AI via SSH.

Usage:
    python scripts/finetune/pipeline_tui.py
    python scripts/finetune/pipeline_tui.py --task code --domain code-generation
"""
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.environ.get("PYTHONPATH", os.path.expanduser("~/mascarade/core")))

from mascarade.finetune.agents.researcher import ResearcherAgent
from mascarade.finetune.agents.documentalist import DocumentalistAgent
from mascarade.finetune.agents.teacher import TeacherAgent, TeacherConfig
from mascarade.finetune.registry import FinetuneRegistry, ModelEntry, DatasetEntry, RunEntry

# ANSI
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

HF_TOKEN = os.environ.get("HUGGINGFACE_API_KEY", "")
KXKM_SSH = "kxkm@kxkm-ai"
KXKM_VENV = "~/mascarade/core/.venv/bin/python"
LOG_DIR = Path("~/.mascarade/finetune/logs").expanduser()
LOG_DIR.mkdir(parents=True, exist_ok=True)


class PipelineLogger:
    """Logs pipeline events to file + terminal."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.log_file = LOG_DIR / f"{run_id}.log"
        self.start_time = time.time()
        self._f = open(self.log_file, "w")
        self._write(f"Pipeline {run_id} started at {datetime.now().isoformat()}")

    def phase(self, name: str):
        elapsed = time.time() - self.start_time
        msg = f"[{elapsed:6.1f}s] ═══ PHASE: {name} ═══"
        print(f"\n{BOLD}{CYAN}{msg}{RESET}")
        self._write(msg)

    def info(self, text: str):
        elapsed = time.time() - self.start_time
        msg = f"[{elapsed:6.1f}s] {text}"
        print(f"  {msg}")
        self._write(msg)

    def ok(self, text: str):
        elapsed = time.time() - self.start_time
        msg = f"[{elapsed:6.1f}s] OK: {text}"
        print(f"  {GREEN}✓{RESET} {text}")
        self._write(msg)

    def warn(self, text: str):
        elapsed = time.time() - self.start_time
        msg = f"[{elapsed:6.1f}s] WARN: {text}"
        print(f"  {YELLOW}⚠{RESET} {text}")
        self._write(msg)

    def fail(self, text: str):
        elapsed = time.time() - self.start_time
        msg = f"[{elapsed:6.1f}s] FAIL: {text}"
        print(f"  {RED}✗{RESET} {text}")
        self._write(msg)

    def data(self, key: str, value):
        self._write(f"  DATA {key}={json.dumps(value, default=str)}")

    def close(self, status: str = "completed"):
        elapsed = time.time() - self.start_time
        msg = f"Pipeline {self.run_id} {status} in {elapsed:.1f}s"
        self._write(msg)
        self._f.close()
        return str(self.log_file)

    def _write(self, text: str):
        self._f.write(text + "\n")
        self._f.flush()


def ssh_cmd(cmd: str, timeout: int = 300) -> tuple[int, str]:
    """Run command on KXKM-AI via SSH."""
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", KXKM_SSH, cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode, result.stdout + result.stderr


def header(text: str):
    print(f"\n{BOLD}{BLUE}╔{'═'*58}╗{RESET}")
    print(f"{BOLD}{BLUE}║  {text:56s}║{RESET}")
    print(f"{BOLD}{BLUE}╚{'═'*58}╝{RESET}")


def input_with_default(prompt: str, default: str) -> str:
    raw = input(f"  {prompt} [{CYAN}{default}{RESET}] > ").strip()
    return raw or default


def input_float(prompt: str, default: float) -> float:
    raw = input(f"  {prompt} [{CYAN}{default}{RESET}] > ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"  {YELLOW}⚠ Invalide, utilisation de {default}{RESET}")
        return default


def input_int(prompt: str, default: int) -> int:
    raw = input(f"  {prompt} [{CYAN}{default}{RESET}] > ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"  {YELLOW}⚠ Invalide, utilisation de {default}{RESET}")
        return default


async def phase_research(log: PipelineLogger, task: str, max_size: float, top_k: int) -> dict | None:
    log.phase("RECHERCHE MODÈLES")
    researcher = ResearcherAgent(hf_token=HF_TOKEN)
    try:
        report = await researcher.recommend(task, max_size_gb=max_size, top_k=top_k)
    except Exception as e:
        log.fail(f"Recherche échouée: {e}")
        return None

    if not report["candidates"]:
        log.fail("Aucun modèle trouvé")
        return None

    for i, m in enumerate(report["candidates"], 1):
        log.info(f"  {i}. {CYAN}{m['model_id']}{RESET}  ↓{m['downloads']:,}  ♥{m['likes']:,}  {m['license']}")
    log.data("model_candidates", [c["model_id"] for c in report["candidates"]])

    if report.get("papers"):
        log.info(f"{DIM}Papers:{RESET}")
        for p in report["papers"][:3]:
            log.info(f"  {DIM}• {p['title'][:70]}{RESET}")

    log.ok(f"Top: {report['candidates'][0]['model_id']}")
    return report


async def phase_dataset(log: PipelineLogger, domain: str, top_k: int) -> dict | None:
    log.phase("RECHERCHE DATASETS")
    doc = DocumentalistAgent(hf_token=HF_TOKEN)
    try:
        report = await doc.recommend(domain, top_k=top_k)
    except Exception as e:
        log.fail(f"Recherche échouée: {e}")
        return None

    if not report["candidates"]:
        log.fail("Aucun dataset trouvé")
        return None

    for i, d in enumerate(report["candidates"], 1):
        log.info(f"  {i}. {CYAN}{d['dataset_id']}{RESET}  ↓{d['downloads']:,}")
    log.data("dataset_candidates", [c["dataset_id"] for c in report["candidates"]])
    log.ok(f"Top: {report['candidates'][0]['dataset_id']}")
    return report


async def phase_teacher(log: PipelineLogger, domain: str) -> str | None:
    log.phase("GÉNÉRATION TEACHER DATA")
    try:
        from mascarade.router import Router
        router = Router()
        if not router._providers:
            log.warn("Aucun provider LLM configuré, skip teacher")
            return None

        teacher = TeacherAgent(router=router)
        config = TeacherConfig(
            task_description=f"Generate high-quality {domain} training data",
        )

        prompts = [
            f"Write a {domain} example with clear instruction and response.",
            f"Create a challenging {domain} task with a detailed solution.",
            f"Generate a {domain} question that tests understanding.",
            f"Provide a step-by-step {domain} tutorial with code.",
            f"Create an advanced {domain} problem and its optimal solution.",
        ]

        output_path = Path(f"~/.mascarade/finetune/teacher/{domain}/train.jsonl").expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        log.info(f"Génération de {len(prompts)} samples via {router._providers.keys()}...")
        result = await teacher.generate_from_prompts(prompts, config, output_path)
        log.ok(f"{result['total']} samples générés → {result['output_path']}")
        log.data("teacher_result", result)
        return result["output_path"]

    except ImportError:
        log.warn("Router non disponible, skip teacher")
        return None
    except Exception as e:
        log.fail(f"Teacher échoué: {e}")
        return None


def phase_check_kxkm(log: PipelineLogger) -> bool:
    log.phase("VÉRIFICATION KXKM-AI")

    log.info("Connexion SSH...")
    rc, out = ssh_cmd("echo OK", timeout=10)
    if rc != 0:
        log.fail(f"SSH failed: {out.strip()}")
        return False
    log.ok("SSH OK")

    log.info("GPU check...")
    rc, out = ssh_cmd(f"{KXKM_VENV} -c 'import torch; print(torch.cuda.get_device_name(0))'", timeout=15)
    if rc != 0:
        log.fail(f"GPU check failed: {out.strip()}")
        return False
    log.ok(f"GPU: {out.strip()}")

    log.info("Packages check...")
    rc, out = ssh_cmd(f"{KXKM_VENV} -c 'import trl, peft; print(f\"trl={{trl.__version__}} peft={{peft.__version__}}\")'", timeout=15)
    if rc != 0:
        log.fail(f"Packages missing: {out.strip()}")
        return False
    log.ok(f"Packages: {out.strip()}")

    return True


def phase_train(log: PipelineLogger, base_model: str, dataset_id: str, run_id: str,
                max_steps: int = 50, batch_size: int = 2) -> dict:
    log.phase(f"TRAINING SUR KXKM-AI")
    log.info(f"Model: {base_model}")
    log.info(f"Dataset: {dataset_id}")
    log.info(f"Config: QLoRA 4bit, {max_steps} steps, batch={batch_size}, lr=2e-4")

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
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"],
    task_type="CAUSAL_LM",
)

training_args = SFTConfig(
    output_dir=output_dir,
    num_train_epochs=1,
    per_device_train_batch_size={batch_size},
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    bf16=True,
    logging_steps=5,
    save_strategy="no",
    report_to="none",
    max_steps={max_steps},
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
    "max_steps": {max_steps},
    "output_dir": output_dir,
    "status": "completed",
}}
print("RESULT_JSON:" + json.dumps(result))
'''

    # Deploy script
    log.info("Deploying training script...")
    script_path = "/tmp/mascarade_train.py"
    proc = subprocess.run(
        ["ssh", KXKM_SSH, f"cat > {script_path}"],
        input=train_script, text=True, timeout=10,
    )
    if proc.returncode != 0:
        log.fail("Failed to deploy script")
        return {"status": "failed", "error": "deploy failed"}
    log.ok("Script deployed")

    # Run training
    log.info("Training en cours...")
    try:
        result = subprocess.run(
            ["ssh", KXKM_SSH, f"{KXKM_VENV} {script_path}"],
            capture_output=True, text=True, timeout=1800,
        )

        for line in result.stdout.split("\n"):
            if line.strip() and "RESULT_JSON:" not in line:
                log.info(f"{DIM}{line.strip()}{RESET}")

        for line in result.stdout.split("\n"):
            if "RESULT_JSON:" in line:
                try:
                    data = json.loads(line.split("RESULT_JSON:")[1])
                except json.JSONDecodeError as e:
                    log.fail(f"JSON parse error: {e}")
                    return {"status": "failed", "error": f"JSON parse error: {e}"}
                log.ok(f"Training terminé en {data['training_time_seconds']}s, loss={data['final_loss']}")
                log.data("training_result", data)
                return data

        if result.returncode != 0:
            log.fail("Training failed")
            for line in result.stderr.split("\n")[-10:]:
                if line.strip():
                    log.info(f"{RED}{line.strip()}{RESET}")
            return {"status": "failed", "error": result.stderr[-500:]}

    except subprocess.TimeoutExpired:
        log.fail("Training timeout (30min)")
        return {"status": "failed", "error": "timeout"}

    return {"status": "failed", "error": "no result found"}


def show_logs():
    """Show and manage pipeline logs."""
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print(f"  {DIM}Aucun log trouvé{RESET}")
        return

    print(f"  {BOLD}Logs ({len(logs)}):{RESET}\n")
    for i, log_path in enumerate(logs[:10], 1):
        size = log_path.stat().st_size
        mtime = datetime.fromtimestamp(log_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        # Read first and last lines for status
        lines = log_path.read_text().strip().split("\n")
        status = "..."
        for line in reversed(lines):
            if "completed" in line.lower():
                status = f"{GREEN}completed{RESET}"
                break
            elif "failed" in line.lower() or "FAIL" in line:
                status = f"{RED}failed{RESET}"
                break

        print(f"  {BOLD}{i}{RESET}. {log_path.name:40s} {mtime}  {size:>6d}B  {status}")

    print(f"\n  {BOLD}v{RESET}=voir  {BOLD}d{RESET}=supprimer  {BOLD}D{RESET}=tout supprimer  {BOLD}0{RESET}=retour")
    try:
        choice = input(f"\n  Action > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "d":
        try:
            idx = int(input(f"  Numéro > ").strip()) - 1
            if 0 <= idx < len(logs[:10]):
                logs[idx].unlink()
                print(f"  {GREEN}✓ Supprimé: {logs[idx].name}{RESET}")
        except (ValueError, EOFError):
            pass
    elif choice.upper() == "D":
        confirm = input(f"  {RED}Supprimer {len(logs)} logs ? (oui/non) > {RESET}").strip()
        if confirm == "oui":
            for log_path in logs:
                log_path.unlink()
            print(f"  {GREEN}✓ {len(logs)} logs supprimés{RESET}")
    elif choice == "v":
        try:
            idx = int(input(f"  Numéro > ").strip()) - 1
            if 0 <= idx < len(logs[:10]):
                content = logs[idx].read_text()
                print(f"\n{DIM}{'─'*60}{RESET}")
                print(content)
                print(f"{DIM}{'─'*60}{RESET}")
        except (ValueError, EOFError):
            pass


async def run_pipeline():
    """Full pipeline with interactive config."""
    header("MASCARADE FINE-TUNING PIPELINE")

    task = input_with_default("Task", "code")
    domain = input_with_default("Domain", "code-generation")
    max_size = input_float("Max model size (GB)", 3.0)
    top_k = input_int("Top K résultats", 5)
    max_steps = input_int("Max training steps", 50)
    batch_size = input_int("Batch size", 2)
    skip_teacher = input_with_default("Skip teacher? (y/n)", "n") == "y"

    run_id = f"ft-{task}-{int(time.time())}"
    registry = FinetuneRegistry()
    log = PipelineLogger(run_id)

    log.info(f"Run ID: {run_id}")
    log.info(f"Config: task={task} domain={domain} max_size={max_size}GB steps={max_steps}")

    # Phase 1: Research
    model_report = await phase_research(log, task, max_size, top_k)
    if not model_report:
        log.close("failed")
        return

    selected_model = model_report["candidates"][0]["model_id"]
    # Allow override
    override = input(f"\n  Modèle [{CYAN}{selected_model}{RESET}] (entrée=garder) > ").strip()
    if override:
        selected_model = override
    log.ok(f"Modèle: {selected_model}")

    # Save to registry
    best = model_report["candidates"][0]
    registry.add_model(ModelEntry(
        model_id=selected_model, source="huggingface", task=task,
        size_gb=best.get("size_gb", 0), license=best.get("license", ""),
        downloads=best.get("downloads", 0),
    ))

    # Phase 2: Dataset
    ds_report = await phase_dataset(log, domain, top_k)
    if not ds_report:
        log.close("failed")
        return

    selected_dataset = ds_report["candidates"][0]["dataset_id"]
    override = input(f"\n  Dataset [{CYAN}{selected_dataset}{RESET}] (entrée=garder) > ").strip()
    if override:
        selected_dataset = override
    log.ok(f"Dataset: {selected_dataset}")

    registry.add_dataset(DatasetEntry(
        dataset_id=selected_dataset, source="huggingface", domain=domain,
        license=ds_report["candidates"][0].get("license", ""),
    ))

    # Phase 3: Teacher (optional)
    if not skip_teacher:
        teacher_path = await phase_teacher(log, domain)
        if teacher_path:
            log.ok(f"Teacher data: {teacher_path}")
    else:
        log.info("Teacher phase skippée")

    # Phase 4: Check KXKM
    if not phase_check_kxkm(log):
        log.warn("KXKM-AI non disponible")
        dry = input(f"  Continuer en dry-run ? (y/n) > ").strip()
        if dry != "y":
            log.close("aborted")
            return
        log.info("Dry-run: skip training")
        log.close("dry-run")
        return

    # Phase 5: Training
    result = phase_train(log, selected_model, selected_dataset, run_id,
                         max_steps=max_steps, batch_size=batch_size)

    # Phase 6: Save to registry
    log.phase("SAUVEGARDE REGISTRE")
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
    log.ok(f"Run {run_id} saved")

    # Summary
    log.phase("RÉSULTAT")
    status = result.get("status", "unknown")
    status_color = GREEN if status == "completed" else RED
    log.info(f"Status: {status_color}{status}{RESET}")
    log.info(f"Model: {selected_model}")
    log.info(f"Dataset: {selected_dataset}")
    log.info(f"Method: {result.get('method', '-')}")
    log.info(f"Loss: {result.get('final_loss', '-')}")
    log.info(f"Time: {result.get('training_time_seconds', '-')}s")

    log_path = log.close(status)
    print(f"\n  {DIM}Log: {log_path}{RESET}\n")


async def main_loop():
    print(f"\n{BOLD}{BLUE}╔══════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{BLUE}║  mascarade Pipeline TUI  v0.2        ║{RESET}")
    print(f"{BOLD}{BLUE}╚══════════════════════════════════════╝{RESET}")

    while True:
        header("MENU PRINCIPAL")
        options = [
            "Lancer pipeline complet",
            "Voir/gérer logs",
            "Status KXKM-AI",
        ]
        for i, opt in enumerate(options, 1):
            print(f"  {BOLD}{i}{RESET}. {opt}")
        print(f"  {BOLD}0{RESET}. Quitter")

        try:
            choice = input(f"\n  Choix > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice in ("0", "q"):
            break
        elif choice == "1":
            await run_pipeline()
        elif choice == "2":
            show_logs()
        elif choice == "3":
            log = PipelineLogger(f"check-{int(time.time())}")
            ok = phase_check_kxkm(log)
            log_path = log.close("ok" if ok else "failed")
            # Clean check logs immediately
            Path(log_path).unlink(missing_ok=True)

    print(f"\n  {DIM}Au revoir!{RESET}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print(f"\n  {DIM}Interrompu.{RESET}\n")
