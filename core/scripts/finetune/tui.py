#!/usr/bin/env python3
"""Fine-tuning TUI — interactive terminal interface for the pipeline.

Usage:
    python scripts/finetune/tui.py
"""

import asyncio
import os
import subprocess
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH", os.path.expanduser("~/mascarade/core")))

from mascarade.finetune.agents.documentalist import DocumentalistAgent
from mascarade.finetune.agents.researcher import ResearcherAgent
from mascarade.finetune.registry import DatasetEntry, FinetuneRegistry, ModelEntry

HF_TOKEN = os.environ.get("HUGGINGFACE_API_KEY", "")

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
RESET = "\033[0m"
BLUE = "\033[34m"


def header(text: str):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}\n")


def success(text: str):
    print(f"  {GREEN}✓{RESET} {text}")


def warn(text: str):
    print(f"  {YELLOW}⚠{RESET} {text}")


def error(text: str):
    print(f"  {RED}✗{RESET} {text}")


def info(text: str):
    print(f"  {DIM}{text}{RESET}")


def menu_choice(options: list[str], prompt: str = "Choix") -> int:
    for i, opt in enumerate(options, 1):
        print(f"  {BOLD}{i}{RESET}. {opt}")
    print(f"  {BOLD}0{RESET}. Retour / Quitter")
    while True:
        try:
            choice = input(f"\n  {prompt} > ").strip()
            if choice == "0" or choice.lower() in ("q", "quit", "exit"):
                return 0
            n = int(choice)
            if 1 <= n <= len(options):
                return n
        except (ValueError, EOFError):
            pass
        print(f"  {RED}Choix invalide{RESET}")


async def do_research():
    header("RECHERCHE — Modèles & Datasets")
    task = (
        input(f"  Task (text-generation/code/embeddings) [{CYAN}code{RESET}] > ").strip() or "code"
    )
    domain = (
        input(
            f"  Domain (code-generation/electronics/french) [{CYAN}code-generation{RESET}] > "
        ).strip()
        or "code-generation"
    )
    try:
        max_size = float(input(f"  Max size GB [{CYAN}4.0{RESET}] > ").strip() or "4.0")
    except ValueError:
        warn("Valeur invalide, utilisation de 4.0 GB")
        max_size = 4.0
    try:
        top_k = int(input(f"  Top K [{CYAN}5{RESET}] > ").strip() or "5")
    except ValueError:
        warn("Valeur invalide, utilisation de 5")
        top_k = 5

    registry = FinetuneRegistry()
    researcher = ResearcherAgent(hf_token=HF_TOKEN)
    documentalist = DocumentalistAgent(hf_token=HF_TOKEN)

    print(f"\n  {DIM}Recherche modèles...{RESET}")
    model_report = await researcher.recommend(task, max_size_gb=max_size, top_k=top_k)

    print(f"\n  {BOLD}Modèles trouvés:{RESET}")
    for i, m in enumerate(model_report["candidates"], 1):
        dl = f"{m['downloads']:,}"
        print(
            f"    {BOLD}{i}{RESET}. {CYAN}{m['model_id']}{RESET}  ↓{dl}  ♥{m['likes']:,}  {m['license']}"
        )
        registry.add_model(
            ModelEntry(
                model_id=m["model_id"],
                source="huggingface",
                task=task,
                size_gb=m["size_gb"],
                license=m["license"],
                downloads=m["downloads"],
            )
        )

    if model_report["papers"]:
        print(f"\n  {BOLD}Papers:{RESET}")
        for p in model_report["papers"][:3]:
            print(f"    {DIM}• {p['title'][:70]}{RESET}")

    print(f"\n  {DIM}Recherche datasets...{RESET}")
    ds_report = await documentalist.recommend(domain, top_k=top_k)

    print(f"\n  {BOLD}Datasets trouvés:{RESET}")
    for i, d in enumerate(ds_report["candidates"], 1):
        dl = f"{d['downloads']:,}"
        print(f"    {BOLD}{i}{RESET}. {CYAN}{d['dataset_id']}{RESET}  ↓{dl}  ♥{d['likes']:,}")
        registry.add_dataset(
            DatasetEntry(
                dataset_id=d["dataset_id"],
                source="huggingface",
                domain=domain,
                license=d["license"],
            )
        )

    success(f"Registry mis à jour: {registry.path}")


async def do_registry():
    header("REGISTRE — Artifacts locaux")
    registry = FinetuneRegistry()

    if registry.models:
        print(f"  {BOLD}Modèles ({len(registry.models)}):{RESET}")
        for mid, m in registry.models.items():
            print(f"    {CYAN}{mid}{RESET}  task={m.task}  size={m.size_gb}GB  dl={m.downloads:,}")
    else:
        warn("Aucun modèle enregistré")

    if registry.datasets:
        print(f"\n  {BOLD}Datasets ({len(registry.datasets)}):{RESET}")
        for did, d in registry.datasets.items():
            print(f"    {CYAN}{did}{RESET}  domain={d.domain}  license={d.license}")
    else:
        warn("Aucun dataset enregistré")

    if registry.runs:
        print(f"\n  {BOLD}Runs ({len(registry.runs)}):{RESET}")
        for rid, r in registry.runs.items():
            status_color = (
                GREEN if r.status == "completed" else (RED if r.status == "failed" else YELLOW)
            )
            print(
                f"    {status_color}{r.status}{RESET}  {rid}  {r.base_model} + {r.dataset}  method={r.method}"
            )
    else:
        info("Aucun run enregistré")


async def do_mesh_status():
    header("MESH P2P — Status des nœuds")

    nodes = {
        "VM (bootstrap)": ("root@192.168.0.119", "4002", "docker, p2p-relay, compute"),
        "GrosMac (bridge)": ("local", "4001", "p2p-relay, p2p-bridge, llm-inference"),
        "CILS": ("cils@192.168.0.210", "4001", "compute"),
        "Tower": ("clems@192.168.0.120", "4001", "compute, storage"),
        "KXKM-AI": ("kxkm@kxkm-ai", "4001", "llm-inference, gpu, compute, ft-student"),
    }

    for name, (host, port, caps) in nodes.items():
        if host == "local":
            status = f"{GREEN}LOCAL{RESET}"
        else:
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-o",
                        "ConnectTimeout=2",
                        "-o",
                        "BatchMode=yes",
                        host,
                        f"lsof -ti:{port}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                status = (
                    f"{GREEN}UP{RESET}"
                    if result.returncode == 0 and result.stdout.strip()
                    else f"{RED}DOWN{RESET}"
                )
            except Exception:
                status = f"{RED}DOWN{RESET}"
        print(f"  {status:>20s}  {BOLD}{name:20s}{RESET} :{port}  [{caps}]")


async def do_train_info():
    header("TRAINING — Info KXKM-AI")
    print(f"  {DIM}Vérification GPU et packages...{RESET}")
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=5",
                "kxkm@kxkm-ai",
                'cd ~/mascarade/core && .venv/bin/python -c "'
                "import torch; "
                "print(f'GPU: {torch.cuda.get_device_name(0)}'); "
                "print(f'CUDA: {torch.version.cuda}'); "
                "import trl, peft; "
                "print(f'trl={trl.__version__} peft={peft.__version__}'); "
                '"',
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout.strip() or result.stderr.strip()
        for line in output.split("\n"):
            if line.strip():
                print(f"  {line.strip()}")
    except Exception as e:
        error(f"Connexion KXKM-AI échouée: {e}")


async def main_loop():
    print(f"\n{BOLD}{BLUE}╔══════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{BLUE}║   mascarade Fine-Tuning TUI  v0.1    ║{RESET}")
    print(f"{BOLD}{BLUE}╚══════════════════════════════════════╝{RESET}")

    while True:
        header("MENU PRINCIPAL")
        choice = menu_choice(
            [
                "Recherche modèles & datasets (HuggingFace)",
                "Voir registre local",
                "Status mesh P2P",
                "Info training node (KXKM-AI)",
            ]
        )

        if choice == 0:
            print(f"\n  {DIM}Au revoir!{RESET}\n")
            break
        elif choice == 1:
            await do_research()
        elif choice == 2:
            await do_registry()
        elif choice == 3:
            await do_mesh_status()
        elif choice == 4:
            await do_train_info()


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print(f"\n  {DIM}Interrompu.{RESET}\n")
