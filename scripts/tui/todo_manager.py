#!/usr/bin/env python3
"""Mascarade TODO Manager — gestionnaire interactif des items ouverts.

Affiche tous les TODOs F*/I*/C*/O*/X* avec filtres par domaine et priorite.

Usage:
    python scripts/tui/todo_manager.py
    python scripts/tui/todo_manager.py --domain finetune
    python scripts/tui/todo_manager.py --priority haute
    python scripts/tui/todo_manager.py --export markdown
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Literal

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Dependances manquantes — pip install rich")
    sys.exit(1)

CONSOLE = Console()

Priority = Literal["CRITIQUE", "HAUTE", "MOYENNE", "FAIBLE", "N/A"]
Domain = Literal["ANE", "Finetune", "Infra", "Cross-repo", "Bloque"]

PRIORITY_ORDER = {"CRITIQUE": 0, "HAUTE": 1, "MOYENNE": 2, "FAIBLE": 3, "N/A": 4}
PRIORITY_STYLE = {
    "CRITIQUE": "bold red",
    "HAUTE":    "bold yellow",
    "MOYENNE":  "bold cyan",
    "FAIBLE":   "dim white",
    "N/A":      "dim",
}
DOMAIN_STYLE = {
    "ANE":        "magenta",
    "Finetune":   "green",
    "Infra":      "blue",
    "Cross-repo": "yellow",
    "Bloque":     "red",
}


@dataclass
class TodoItem:
    id: str
    priority: Priority
    description: str
    domain: Domain
    notes: str = ""
    blocked_by: list[str] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    github_forks: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Dataset actif (source de verite)                                             #
# --------------------------------------------------------------------------- #

ALL_TODOS: list[TodoItem] = [
    # ANE
    TodoItem("P1", "CRITIQUE", "run_next_lots.py --lot priority_models sans checkpoint inattendu",
             "ANE", refs=["scripts/run_next_useful_lot.sh"],
             dependencies=["checkpoint_resume", "apple_coreml", "lot_priority_models"]),

    # Fine-tuning / HuggingFace
    TodoItem("F3", "HAUTE", "Push HF Hub clemsail/mascarade-* (adapters)",
             "Finetune", refs=["scripts/publish-hf.sh"],
             dependencies=["huggingface_hub", "HF_TOKEN"],
             github_forks=["electron-rare/mascarade"]),
    TodoItem("F7", "HAUTE", "Push HF Hub clemsail/mascarade-* (modeles finaux)",
             "Finetune", refs=["scripts/publish-hf.sh"],
             dependencies=["huggingface_hub", "HF_TOKEN"],
             github_forks=["electron-rare/mascarade"]),
    TodoItem("F25", "HAUTE", "Archiviste push HF complet (adapters + modeles finaux)",
             "Finetune", refs=["core/mascarade/finetune/agents/archivist.py"],
             dependencies=["huggingface_hub", "archive_manifest", "model_card"],
             github_forks=["electron-rare/mascarade"]),
    TodoItem("F6", "HAUTE", "Red-team + regression CILS sur modeles valides",
             "Finetune", refs=["scripts/benchmark-v4-all.sh"],
             dependencies=["benchmark_suite", "cils_runner"]),
    TodoItem("F8", "HAUTE", "Cycle de recherche hebdo automatise (modeles/datasets)",
             "Finetune", refs=["core/mascarade/finetune/agents/researcher.py"],
             dependencies=["scheduler_weekly", "dataset_refresh"]),
    TodoItem("F9", "HAUTE", "Dataset mascarade-kicad publie sur HuggingFace (2644 rows)",
             "Finetune", refs=["finetune/datasets/build_kicad_dataset.py"],
             dependencies=["kicad_dataset_2644", "huggingface_datasets", "HF_TOKEN"],
             github_forks=["electron-rare/mascarade"]),
    TodoItem("F23", "MOYENNE", "Phase B rejection sampling",
             "Finetune", notes="requis: gcc-arm-none-eabi + ngspice",
             refs=["finetune/rejection_sampling.py"],
             dependencies=["gcc-arm-none-eabi", "ngspice", "rejection_sampling.py"]),
    TodoItem("F29", "MOYENNE", "Test e2e pipeline research > dataset > training sur mesh P2P",
             "Finetune", dependencies=["p2p_mesh", "dataset_builder", "training_runner"]),

    # Infra / Observabilite
    TodoItem("I1", "HAUTE", "Import dashboard Grafana P2P",
             "Infra", refs=["deploy/grafana/"], dependencies=["grafana", "dashboard_json"]),
    TodoItem("I8", "MOYENNE", "Alertes Prometheus peer_count sous seuil",
             "Infra", refs=["deploy/prometheus/"], dependencies=["prometheus", "alert_rules"]),
    TodoItem("I9", "MOYENNE", "Dashboard consolide LLM + P2P + fine-tuning",
             "Infra", dependencies=["grafana", "prometheus", "loki", "tempo"]),
    TodoItem("I11", "FAIBLE", "Integration ZeroClaw + n8n",
             "Infra", dependencies=["zeroclaw", "n8n", "webhooks"]),

    # Backlog conditionnel
    TodoItem("F12", "FAIBLE", "Evaluation Agent Zero — scoping",
             "Finetune", notes="POC isole, garde-fous requis",
             dependencies=["agent_zero_poc", "safety_guardrails"],
             github_forks=["jochemkroon/KiC-AI", "mixelpixx/KiCAD-MCP-Server"]),
    TodoItem("F13", "FAIBLE", "Evaluation Agent Zero — POC isole",
             "Finetune", dependencies=["agent_zero_poc"]),
    TodoItem("F14", "FAIBLE", "Evaluation Agent Zero — garde-fous",
             "Finetune", dependencies=["red_team_checks", "policy_filters"]),
    TodoItem("F20", "FAIBLE", "Benchmark Qwen3-Coder-Next, Mellum-4b, DeepSeek-V3.2",
             "Finetune", dependencies=["benchmark_harness", "model_registry"]),
]


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #

def make_table(items: list[TodoItem], title: str = "TODOs ouverts") -> Table:
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        expand=True,
        title=f"[bold]{title}[/bold]",
        border_style="cyan",
        row_styles=["", "dim"],
    )
    table.add_column("ID", style="bold dim", no_wrap=True, width=6)
    table.add_column("Prio", no_wrap=True, width=9)
    table.add_column("Description", ratio=1)
    table.add_column("Domaine", no_wrap=True, width=12)
    table.add_column("Notes / Refs / Deps / Forks", style="dim", ratio=1)

    sorted_items = sorted(items, key=lambda x: (PRIORITY_ORDER.get(x.priority, 99), x.domain, x.id))
    for item in sorted_items:
        prio_style = PRIORITY_STYLE.get(item.priority, "white")
        domain_style = DOMAIN_STYLE.get(item.domain, "white")
        notes_str = item.notes
        if item.refs:
            notes_str += (" · " if notes_str else "") + ", ".join(item.refs[:2])
        if item.dependencies:
            notes_str += (" · " if notes_str else "") + "deps: " + ", ".join(item.dependencies[:2])
        if item.github_forks:
            notes_str += (" · " if notes_str else "") + "forks: " + ", ".join(item.github_forks[:2])
        if item.blocked_by:
            notes_str += f" [bloque: {', '.join(item.blocked_by)}]"
        table.add_row(
            item.id,
            Text(item.priority, style=prio_style),
            item.description,
            Text(item.domain, style=domain_style),
            notes_str,
        )
    return table


def make_summary(items: list[TodoItem]) -> Panel:
    by_domain: dict[str, list[TodoItem]] = {}
    for item in items:
        by_domain.setdefault(item.domain, []).append(item)

    by_prio: dict[str, list[TodoItem]] = {}
    for item in items:
        by_prio.setdefault(item.priority, []).append(item)

    lines = []
    for prio in ("CRITIQUE", "HAUTE", "MOYENNE", "FAIBLE", "N/A"):
        count = len(by_prio.get(prio, []))
        if count:
            style = PRIORITY_STYLE.get(prio, "white")
            lines.append(f"  [{style}]{prio:10}[/{style}]  {count} items")

    lines.append("")
    for domain, domain_items in sorted(by_domain.items()):
        style = DOMAIN_STYLE.get(domain, "white")
        lines.append(f"  [{style}]{domain:12}[/{style}]  {len(domain_items)} items")

    return Panel(
        "\n".join(lines),
        title=f"[bold]Resume ({len(items)} items)[/bold]",
        border_style="yellow",
        padding=(0, 1),
    )


def export_markdown(items: list[TodoItem]) -> str:
    lines = ["# TODOs ouverts Mascarade\n"]
    sorted_items = sorted(items, key=lambda x: (PRIORITY_ORDER.get(x.priority, 99), x.id))
    current_domain = ""
    for item in sorted_items:
        if item.domain != current_domain:
            current_domain = item.domain
            lines.append(f"\n## {current_domain}\n")
        blocked = f" *(bloque: {', '.join(item.blocked_by)})*" if item.blocked_by else ""
        refs = f" — `{'`, `'.join(item.refs)}`" if item.refs else ""
        deps = f" — deps: `{'`, `'.join(item.dependencies)}`" if item.dependencies else ""
        forks = f" — forks: `{'`, `'.join(item.github_forks)}`" if item.github_forks else ""
        notes = f" ({item.notes})" if item.notes else ""
        lines.append(f"- **{item.id}** [{item.priority}] {item.description}{notes}{refs}{deps}{forks}{blocked}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Interactive loop                                                             #
# --------------------------------------------------------------------------- #

def interactive_mode(items: list[TodoItem]) -> None:
    CONSOLE.print()
    CONSOLE.print("[bold cyan]Mascarade TODO Manager[/bold cyan]  [dim]— q=quitter, h=aide[/dim]\n")

    current = list(items)
    active_domain: str | None = None
    active_priority: str | None = None

    while True:
        CONSOLE.print(make_table(current, title=_filter_label(active_domain, active_priority)))
        CONSOLE.print(make_summary(current))

        try:
            cmd = Prompt.ask(
                "\n[bold cyan]>[/bold cyan] commande",
                default="",
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if cmd in ("q", "quit", "exit"):
            break
        elif cmd == "h" or cmd == "help":
            _print_help()
        elif cmd == "a" or cmd == "all":
            current = list(items)
            active_domain = None
            active_priority = None
        elif cmd.startswith("d ") or cmd.startswith("domain "):
            domain = cmd.split(None, 1)[1].strip().lower()
            current = [x for x in items if x.domain.lower().startswith(domain)]
            active_domain = domain
            active_priority = None
        elif cmd.startswith("p ") or cmd.startswith("prio "):
            prio = cmd.split(None, 1)[1].strip().upper()
            current = [x for x in items if x.priority.upper().startswith(prio)]
            active_priority = prio
            active_domain = None
        elif cmd == "export" or cmd == "md":
            md = export_markdown(current)
            CONSOLE.print(Panel(md, title="Export Markdown", border_style="green"))
        elif cmd == "active":
            current = [x for x in items if x.priority != "N/A"]
            active_domain = None
            active_priority = None
        elif cmd == "blocked":
            current = [x for x in items if x.priority == "N/A"]
            active_domain = None
            active_priority = None
        else:
            CONSOLE.print("[dim]Commande inconnue — 'h' pour l'aide[/dim]")


def _filter_label(domain: str | None, priority: str | None) -> str:
    if domain:
        return f"TODOs — domaine: {domain}"
    if priority:
        return f"TODOs — priorite: {priority}"
    return "Tous les TODOs ouverts"


def _print_help() -> None:
    help_text = """
[bold]Commandes disponibles :[/bold]

  [cyan]a[/cyan], [cyan]all[/cyan]            Afficher tous les items
  [cyan]active[/cyan]           Items actifs (F*/I*/P*, hors bloques)
  [cyan]blocked[/cyan]          Items bloques uniquement (X*, N/A)
  [cyan]d <domain>[/cyan]       Filtrer par domaine (ane, finetune, infra, cross)
  [cyan]p <prio>[/cyan]         Filtrer par priorite (critique, haute, moyenne, faible)
  [cyan]export[/cyan], [cyan]md[/cyan]        Exporter en Markdown
  [cyan]h[/cyan], [cyan]help[/cyan]           Afficher cette aide
  [cyan]q[/cyan], [cyan]quit[/cyan]           Quitter
"""
    CONSOLE.print(Panel(help_text, border_style="dim", padding=(0, 2)))


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Mascarade TODO Manager")
    parser.add_argument("--domain", help="Filtrer par domaine")
    parser.add_argument("--priority", help="Filtrer par priorite")
    parser.add_argument("--export", choices=["markdown"], help="Exporter et quitter")
    parser.add_argument("--active", action="store_true", help="Items actifs seulement")
    parser.add_argument("--blocked", action="store_true", help="Items bloques seulement")
    args = parser.parse_args()

    items = list(ALL_TODOS)

    if args.active:
        items = [x for x in items if x.priority != "N/A"]
    elif args.blocked:
        items = [x for x in items if x.priority == "N/A"]

    if args.domain:
        items = [x for x in items if x.domain.lower().startswith(args.domain.lower())]
    if args.priority:
        items = [x for x in items if x.priority.lower().startswith(args.priority.lower())]

    if args.export == "markdown":
        print(export_markdown(items))
        return

    # Mode interactif si terminal
    if sys.stdin.isatty():
        interactive_mode(items)
    else:
        CONSOLE.print(make_table(items))
        CONSOLE.print(make_summary(items))


if __name__ == "__main__":
    main()
