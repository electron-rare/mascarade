#!/usr/bin/env python3
"""Mascarade Finetune Watcher — suivi pipeline fine-tuning en temps reel.

Affiche l'etat de chaque lot (modele, dataset, statut, metriques).
En mode --live, rafraichit toutes les 3s en lisant les logs du repertoire
de sortie fine-tuning.

Usage:
    python scripts/tui/finetune_watcher.py
    python scripts/tui/finetune_watcher.py --live
    python scripts/tui/finetune_watcher.py --stage sft
    python scripts/tui/finetune_watcher.py --output /path/to/output
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from rich import box
    from rich.columns import Columns
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Dependances manquantes — pip install rich")
    sys.exit(1)

CONSOLE = Console()

# --------------------------------------------------------------------------- #
# Config modeles                                                                #
# --------------------------------------------------------------------------- #

FINETUNE_MODELS = [
    # id, domaine, examples, stage, statut, machine
    ("mascarade-spice-v3",        "SPICE",          13_723,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-verilog-v1",      "Verilog/RTL",    26_532,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-emc-v2",          "EMC/EMI",         3_016,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-ipc-v2",          "IPC/JLCPCB",      2_251,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-dsp-v2",          "DSP ARM CMSIS",   2_015,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-power-v2",        "Puissance",       1_967,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-kicad-v4",        "KiCad 10",        1_931,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-embedded-v3",     "Embarque",        1_669,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-analog-v2",       "Analogique",      1_249,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-freecad-v1",      "FreeCAD 3D",      3_974,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-platformio-v1",   "PlatformIO",        763,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-missing-v2",      "RF/Securite",       891,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-iot-v2",          "IoT ESP-IDF",       385,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-stm32-v1",        "STM32 HAL",         313,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-stackexchange-ee","StackEx EE",     95_000,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-leetcode-asm",    "LeetCode ASM",   14_000,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-real-code",       "Code reel",       3_600,  "SFT",  "OK",       "KXKM-AI"),
    ("mascarade-cpt-verilog",     "CPT Verilog",   390_000,  "CPT",  "CPT",      "KXKM-AI"),
    ("mascarade-cpt-kicad",       "CPT KiCad",      43_000,  "CPT",  "CPT",      "KXKM-AI"),
    ("mascarade-cpt-semi",        "CPT Semi-cond",  59_000,  "CPT",  "CPT",      "KXKM-AI"),
    # 9 restants en retraining
    ("mascarade-spice-v4",        "SPICE v4",       15_000,  "SFT",  "RETRAIN",  "KXKM-AI"),
    ("mascarade-verilog-v2",      "Verilog v2",     28_000,  "SFT",  "RETRAIN",  "KXKM-AI"),
    ("mascarade-kicad-v5",        "KiCad v5",        2_500,  "SFT",  "RETRAIN",  "KXKM-AI"),
    ("mascarade-embedded-v4",     "Embarque v4",     2_000,  "SFT",  "RETRAIN",  "KXKM-AI"),
    ("mascarade-dsp-v3",          "DSP v3",          2_200,  "SFT",  "RETRAIN",  "KXKM-AI"),
    ("mascarade-power-v3",        "Puissance v3",    2_100,  "SFT",  "RETRAIN",  "KXKM-AI"),
    ("mascarade-rlvr-kicad",      "RLVR KiCad",      1_931,  "RLVR", "QUEUE",    "KXKM-AI"),
    ("mascarade-grpo-verilog",    "GRPO Verilog",   26_532,  "RLVR", "QUEUE",    "KXKM-AI"),
    ("mascarade-dpo-general",     "DPO General",     5_000,  "DPO",  "QUEUE",    "KXKM-AI"),
]

STATUS_STYLE = {
    "OK":      ("bold green",   "✓"),
    "RETRAIN": ("bold yellow",  "↻"),
    "CPT":     ("bold cyan",    "~"),
    "QUEUE":   ("dim",          "…"),
    "ERROR":   ("bold red",     "✗"),
    "RUNNING": ("bold magenta", "▶"),
}

STAGE_STYLE = {
    "CPT":  "cyan",
    "SFT":  "green",
    "RLVR": "magenta",
    "DPO":  "yellow",
    "ORPO": "blue",
}


# --------------------------------------------------------------------------- #
# Log parsing                                                                  #
# --------------------------------------------------------------------------- #

def scan_output_dir(output_dir: Path) -> dict[str, dict[str, Any]]:
    """Scanne le repertoire de sortie pour detecter les runs recents."""
    info: dict[str, dict[str, Any]] = {}
    if not output_dir.exists():
        return info

    for model_dir in sorted(output_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        meta: dict[str, Any] = {}

        # trainer_state.json (HF Transformers)
        state_file = model_dir / "trainer_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                meta["step"] = state.get("global_step", 0)
                meta["max_steps"] = state.get("max_steps", 0)
                history = state.get("log_history", [])
                if history:
                    last = history[-1]
                    meta["loss"] = last.get("loss", last.get("train_loss"))
                    meta["epoch"] = last.get("epoch")
            except Exception:
                pass

        # adapter_config.json — confirme que l'adapter est pret
        adapter = model_dir / "adapter_config.json"
        if adapter.exists():
            meta["adapter"] = True

        if meta:
            info[model_dir.name] = meta

    return info


def detect_running_processes() -> list[str]:
    """Detecte les processus de fine-tuning actifs."""
    try:
        import subprocess
        result = subprocess.run(
            ["pgrep", "-la", "python"],
            capture_output=True, text=True, timeout=3
        )
        lines = result.stdout.strip().splitlines()
        return [l for l in lines if any(kw in l for kw in ("finetune", "train", "trl", "sft", "qlora"))]
    except Exception:
        return []


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #

def make_header() -> Panel:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return Panel(
        Text.assemble(
            Text("⚗  MASCARADE — Pipeline Fine-Tuning\n", style="bold cyan", justify="center"),
            Text(f"  {now}  ·  29 modeles  ·  184K+ exemples", style="dim", justify="center"),
        ),
        style="cyan",
        padding=(0, 2),
    )


def make_progress_summary(models: list) -> Panel:
    by_status: dict[str, int] = {}
    for m in models:
        by_status[m[4]] = by_status.get(m[4], 0) + 1

    total = len(models)
    ok = by_status.get("OK", 0)
    retrain = by_status.get("RETRAIN", 0)
    cpt = by_status.get("CPT", 0)
    queue = by_status.get("QUEUE", 0)

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        expand=True,
    )
    task = progress.add_task("[green]Termines OK", total=total, completed=ok)
    progress.add_task("[yellow]Retraining", total=total, completed=retrain)
    progress.add_task("[cyan]CPT", total=total, completed=cpt)
    progress.add_task("[dim]En queue", total=total, completed=queue)

    return Panel(progress, title="[bold]Progression globale[/bold]", border_style="green")


def make_model_table(
    models: list,
    stage_filter: str | None = None,
    output_info: dict | None = None,
) -> Table:
    if stage_filter:
        models = [m for m in models if m[3].upper() == stage_filter.upper()]

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        expand=True,
        border_style="blue",
    )
    table.add_column("Modele", style="bold", no_wrap=True)
    table.add_column("Domaine", style="dim")
    table.add_column("Exemples", justify="right")
    table.add_column("Stage", justify="center", no_wrap=True)
    table.add_column("Statut", justify="center", no_wrap=True)
    table.add_column("Machine", style="dim", no_wrap=True)
    table.add_column("Info", style="dim")

    for model_id, domain, examples, stage, status, machine in models:
        stage_style = STAGE_STYLE.get(stage, "white")
        status_style, status_icon = STATUS_STYLE.get(status, ("white", "?"))

        # Enrichissement depuis les logs si disponible
        extra = ""
        if output_info and model_id in output_info:
            meta = output_info[model_id]
            if "step" in meta and "max_steps" in meta and meta["max_steps"]:
                pct = int(100 * meta["step"] / meta["max_steps"])
                extra = f"step {meta['step']}/{meta['max_steps']} ({pct}%)"
            if "loss" in meta and meta["loss"] is not None:
                extra += f" loss={meta['loss']:.4f}"
            if meta.get("adapter"):
                extra += " [adapter✓]"

        table.add_row(
            model_id,
            domain,
            f"{examples:,}",
            Text(stage, style=stage_style),
            Text(f"{status_icon} {status}", style=status_style),
            machine,
            extra,
        )

    return table


def make_active_runs(processes: list[str]) -> Panel:
    if not processes:
        body = Text("Aucun processus de training detecte", style="dim italic")
    else:
        lines = []
        for p in processes[:10]:
            lines.append(Text(f"  ● {p[:100]}", style="bold magenta"))
        body = Text.assemble(*[Text.assemble(l, "\n") for l in lines])
    return Panel(body, title="[bold magenta]Processus actifs[/bold magenta]", border_style="magenta")


def make_agents_status() -> Panel:
    agents = [
        ("researcher",    "Recherche modeles/datasets",   "8 agents pipeline"),
        ("preparateur",   "Preparation datasets",         "QLoRA/DPO/ORPO"),
        ("entraineur",    "Training (TRL/Unsloth)",        "GRPO/ReinforcerAgent"),
        ("evaluateur",    "Evaluation (benchmarks)",       "Codestral juge"),
        ("validateur",    "Validation (red-team)",         "CILS integration"),
        ("archiviste",    "Publication HuggingFace",       "clemsail/mascarade-*"),
        ("documentalist", "Documentation",                 "auto-generated"),
        ("reinforcer",    "GRPO training",                 "train_grpo() :203-304"),
    ]
    table = Table(box=box.SIMPLE, show_header=False, expand=True, padding=(0, 1))
    table.add_column("Agent", style="bold green", no_wrap=True)
    table.add_column("Role", style="dim")
    table.add_column("Notes", style="dim italic")
    for agent, role, notes in agents:
        table.add_row(agent, role, notes)
    return Panel(table, title="[bold]Agents pipeline finetune (8)[/bold]", border_style="green")


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def render(stage: str | None, output_dir: Path) -> None:
    output_info = scan_output_dir(output_dir)
    processes = detect_running_processes()

    CONSOLE.print(make_header())
    CONSOLE.print(make_progress_summary(FINETUNE_MODELS))
    CONSOLE.print()
    title_suffix = f" — stage: {stage.upper()}" if stage else " — tous les stages"
    CONSOLE.print(
        Panel(
            make_model_table(FINETUNE_MODELS, stage, output_info),
            title=f"[bold]Modeles fine-tuning{title_suffix}[/bold]",
            border_style="blue",
        )
    )
    CONSOLE.print(make_active_runs(processes))
    CONSOLE.print(make_agents_status())


def main() -> None:
    parser = argparse.ArgumentParser(description="Mascarade Finetune Watcher")
    parser.add_argument("--live", action="store_true", help="Mode live (refresh 3s)")
    parser.add_argument("--stage", choices=["cpt", "sft", "rlvr", "dpo", "orpo"],
                        help="Filtrer par stage")
    parser.add_argument(
        "--output",
        default=os.path.join(os.path.dirname(__file__), "../../output"),
        help="Repertoire de sortie training",
    )
    args = parser.parse_args()
    output_dir = Path(args.output).resolve()
    stage = args.stage.upper() if args.stage else None

    if args.live:
        with Live(screen=True, refresh_per_second=0.3) as live:
            try:
                while True:
                    output_info = scan_output_dir(output_dir)
                    processes = detect_running_processes()
                    from rich.console import Group
                    live.update(
                        Group(
                            make_header(),
                            make_progress_summary(FINETUNE_MODELS),
                            Panel(
                                make_model_table(FINETUNE_MODELS, stage, output_info),
                                title="[bold]Modeles fine-tuning[/bold]",
                                border_style="blue",
                            ),
                            make_active_runs(processes),
                        )
                    )
                    time.sleep(3)
            except KeyboardInterrupt:
                pass
    else:
        render(stage, output_dir)


if __name__ == "__main__":
    main()
