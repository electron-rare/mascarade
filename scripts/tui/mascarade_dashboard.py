#!/usr/bin/env python3
"""Mascarade Dashboard — tableau de bord global temps réel.

Usage:
    python scripts/tui/mascarade_dashboard.py
    python scripts/tui/mascarade_dashboard.py --live      # refresh toutes les 5s
    python scripts/tui/mascarade_dashboard.py --host http://localhost:8100
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from typing import Any

try:
    import httpx
    from rich import box
    from rich.columns import Columns
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Dependances manquantes — pip install rich httpx")
    sys.exit(1)

CONSOLE = Console()

# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #

MACHINES = [
    {"name": "Tower", "host": "clems@tower", "role": "Serveur principal (La Suite, Ollama CPU)", "gpu": "Quadro P2000"},
    {"name": "KXKM-AI", "host": "kxkm@kxkm-ai", "role": "Inference GPU, fine-tuning", "gpu": "RTX 4090 24GB"},
    {"name": "Photon", "host": "cils@192.168.0.119", "role": "Traefik proxy, Cloudflare", "gpu": "--"},
    {"name": "GrosMac", "host": "192.168.0.210", "role": "Dev (Apple M5 ANE)", "gpu": "Apple M5"},
    {"name": "CILS", "host": "localhost", "role": "Recherche web (SearXNG)", "gpu": "--"},
]

PROD_AGENTS = [
    "ops-monitor", "ops-deployer", "ops-incident",
    "ops-healthcheck", "ops-security", "web-researcher",
    "lead-scorer", "dolibarr-assistant", "grist-data",
]

OPEN_TODOS = [
    ("P1",  "CRITIQUE", "run_next_lots.py --lot priority_models",                "ANE"),
    ("F3",  "HAUTE",    "Push HF Hub clemsail/mascarade-* adapters",             "Finetune"),
    ("F6",  "HAUTE",    "Red-team + regression CILS sur modeles valides",        "Finetune"),
    ("F8",  "HAUTE",    "Cycle recherche hebdo automatise",                      "Finetune"),
    ("F9",  "HAUTE",    "Dataset mascarade-kicad -> HuggingFace (2644 rows)",    "Finetune"),
    ("F23", "MOYENNE",  "Phase B rejection sampling",                            "Finetune"),
    ("F29", "MOYENNE",  "Test e2e pipeline research > dataset > training P2P",   "Finetune"),
    ("I1",  "HAUTE",    "Import dashboard Grafana P2P",                          "Infra"),
    ("I8",  "MOYENNE",  "Alertes Prometheus peer_count sous seuil",              "Infra"),
    ("I9",  "MOYENNE",  "Dashboard consolide LLM + P2P + fine-tuning",          "Infra"),
    ("I11", "FAIBLE",   "Integration ZeroClaw + n8n",                           "Infra"),
]

PRIORITY_COLORS = {"CRITIQUE": "red", "HAUTE": "yellow", "MOYENNE": "cyan", "FAIBLE": "dim"}


# --------------------------------------------------------------------------- #
# Data fetching                                                                #
# --------------------------------------------------------------------------- #

def fetch_core(host: str) -> dict[str, Any]:
    try:
        r = httpx.get(f"{host}/health", timeout=2.0)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def ping_ssh(host_alias: str, timeout: int = 2) -> bool:
    """Retourne True si la machine repond au ping SSH."""
    if host_alias in ("localhost", "192.168.0.210", "192.168.0.119"):
        cmd = ["ping", "-c", "1", "-W", str(timeout * 1000), host_alias.split("@")[-1]]
    else:
        cmd = ["ssh", "-o", "ConnectTimeout=2", "-o", "BatchMode=yes", host_alias, "uptime"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 1)
        return r.returncode == 0
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Render panels                                                                #
# --------------------------------------------------------------------------- #

def make_header() -> Panel:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = Text("⬡  MASCARADE v0.3.0", style="bold cyan", justify="center")
    sub = Text(f"Tableau de bord operateur  ·  {now}", style="dim", justify="center")
    return Panel(Text.assemble(title, "\n", sub), style="cyan", padding=(0, 2))


def make_stats() -> Panel:
    stats = [
        ("Agents",    "242",    "blueviolet"),
        ("En prod",   "9",      "green"),
        ("Providers", "25+",    "cyan"),
        ("MCP",       "299",    "yellow"),
        ("P2P nodes", "5",      "magenta"),
        ("Services",  "42",     "blue"),
        ("Tests",     "2500+",  "bright_green"),
        ("Modeles",   "29",     "bright_magenta"),
    ]
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    row1, row2 = [], []
    for i, (label, value, color) in enumerate(stats):
        cell = Text.assemble(
            Text(f" {value}\n", style=f"bold {color}"),
            Text(f" {label}", style="dim"),
        )
        if i < 4:
            row1.append(cell)
        else:
            row2.append(cell)
    table.add_row(*row1)
    table.add_row(*row2)
    return Panel(table, title="[bold]Metriques globales[/bold]", border_style="blue", padding=(0, 1))


def make_machines(check_ssh: bool = False) -> Panel:
    table = Table(box=box.SIMPLE_HEAD, show_header=True, expand=True)
    table.add_column("Machine", style="bold cyan", no_wrap=True)
    table.add_column("Role", style="white")
    table.add_column("GPU", style="dim")
    table.add_column("Status", justify="center")

    for m in MACHINES:
        if check_ssh:
            alive = ping_ssh(m["host"])
            status = Text("● UP", style="green") if alive else Text("● DOWN", style="red")
        else:
            status = Text("?", style="dim")
        table.add_row(m["name"], m["role"], m["gpu"], status)

    return Panel(table, title="[bold]Infrastructure P2P (5 noeuds)[/bold]", border_style="magenta")


def make_agents() -> Panel:
    table = Table(box=box.SIMPLE, show_header=False, expand=True, padding=(0, 1))
    table.add_column("Agent", style="bold green", no_wrap=True)
    table.add_column("Domaine", style="dim")

    domains = {
        "ops-monitor": "Ops", "ops-deployer": "Ops", "ops-incident": "Ops",
        "ops-healthcheck": "Ops", "ops-security": "Ops",
        "web-researcher": "Research", "lead-scorer": "Sales",
        "dolibarr-assistant": "ERP", "grist-data": "Data",
    }
    for agent in PROD_AGENTS:
        table.add_row(f"● {agent}", domains.get(agent, "?"))

    return Panel(table, title="[bold]Agents production (9)[/bold]", border_style="green")


def make_todos() -> Panel:
    table = Table(box=box.SIMPLE_HEAD, show_header=True, expand=True)
    table.add_column("ID", style="bold dim", no_wrap=True, width=5)
    table.add_column("Priorite", no_wrap=True, width=10)
    table.add_column("Description", ratio=1)
    table.add_column("Domaine", style="dim", no_wrap=True)

    for todo_id, prio, desc, domain in OPEN_TODOS:
        color = PRIORITY_COLORS.get(prio, "white")
        table.add_row(
            todo_id,
            Text(prio, style=f"bold {color}"),
            desc,
            domain,
        )

    return Panel(
        table,
        title=f"[bold]TODOs ouverts ({len(OPEN_TODOS)})[/bold]",
        border_style="yellow",
    )


def make_core_status(data: dict[str, Any]) -> Panel:
    if not data:
        body = Text("Core inaccessible (localhost:8100)", style="dim red")
    else:
        lines = []
        for k, v in data.items():
            lines.append(f"  [dim]{k}[/dim]  [bold cyan]{v}[/bold cyan]")
        body = "\n".join(lines) if lines else "(reponse vide)"
    return Panel(body, title="[bold]Core /health[/bold]", border_style="cyan")


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #

def build_layout(host: str, check_ssh: bool) -> Layout:
    core_data = fetch_core(host)

    layout = Layout()
    layout.split_column(
        Layout(make_header(), name="header", size=4),
        Layout(name="body"),
        Layout(make_todos(), name="todos", size=len(OPEN_TODOS) + 4),
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    layout["left"].split_column(
        Layout(make_stats(), name="stats", size=8),
        Layout(make_agents(), name="agents"),
    )
    layout["right"].split_column(
        Layout(make_machines(check_ssh), name="machines"),
        Layout(make_core_status(core_data), name="core", size=6),
    )
    return layout


def main() -> None:
    parser = argparse.ArgumentParser(description="Mascarade Dashboard")
    parser.add_argument("--host", default="http://localhost:8100", help="Core API host")
    parser.add_argument("--live", action="store_true", help="Refresh toutes les 5 secondes")
    parser.add_argument("--ssh", action="store_true", help="Verifier SSH machines (lent)")
    args = parser.parse_args()

    if args.live:
        with Live(build_layout(args.host, args.ssh), refresh_per_second=0.2, screen=True) as live:
            try:
                while True:
                    time.sleep(5)
                    live.update(build_layout(args.host, args.ssh))
            except KeyboardInterrupt:
                pass
    else:
        CONSOLE.print(build_layout(args.host, args.ssh))


if __name__ == "__main__":
    main()
