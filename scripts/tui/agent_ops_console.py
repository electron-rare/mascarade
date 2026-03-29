#!/usr/bin/env python3
"""Mascarade Agent Ops Console — pilotage des lots actifs et des logs.

Usage:
    python scripts/tui/agent_ops_console.py
    python scripts/tui/agent_ops_console.py --export markdown
    python scripts/tui/agent_ops_console.py --purge-old-logs --days 7
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Dependances manquantes — pip install rich")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs/plan/2026-03-28-autonomous-ops/task_registry.json"
ACTION_LOG = REPO_ROOT / "tmp/agent_ops_console.log"
CONSOLE = Console()

PRIORITY_STYLE = {
    "critical": "bold red",
    "high": "bold yellow",
    "medium": "cyan",
    "low": "dim",
}

STATUS_STYLE = {
    "ready": "bold green",
    "in_progress": "bold cyan",
    "blocked": "bold red",
    "done": "dim green",
}


@dataclass
class LogRecord:
    path: Path
    size_bytes: int
    modified_at: datetime


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text())


def append_action_log(message: str) -> None:
    ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with ACTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def scan_logs(paths: list[str], patterns: list[str], older_than_days: int) -> list[LogRecord]:
    threshold = datetime.now() - timedelta(days=older_than_days)
    records: list[LogRecord] = []
    for raw_path in paths:
        base = REPO_ROOT / raw_path
        if not base.exists():
            continue
        for pattern in patterns:
            for candidate in base.rglob(pattern):
                if not candidate.is_file():
                    continue
                stat = candidate.stat()
                modified_at = datetime.fromtimestamp(stat.st_mtime)
                if modified_at <= threshold:
                    records.append(
                        LogRecord(
                            path=candidate,
                            size_bytes=stat.st_size,
                            modified_at=modified_at,
                        )
                    )
    return sorted(records, key=lambda item: item.modified_at)


def purge_logs(records: list[LogRecord]) -> int:
    deleted = 0
    for record in records:
        record.path.unlink(missing_ok=True)
        deleted += 1
    append_action_log(f"purged {deleted} log files")
    return deleted


def make_lots_table(registry: dict) -> Table:
    table = Table(box=box.ROUNDED, expand=True, border_style="cyan")
    table.add_column("Lot", style="bold", no_wrap=True)
    table.add_column("Prio", no_wrap=True)
    table.add_column("Statut", no_wrap=True)
    table.add_column("Agent dédié", no_wrap=True)
    table.add_column("Sous-agents")
    table.add_column("Résumé", ratio=1)
    for lot in registry["lots"]:
        table.add_row(
            lot["id"],
            Text(lot["priority"].upper(), style=PRIORITY_STYLE.get(lot["priority"], "white")),
            Text(lot["status"], style=STATUS_STYLE.get(lot["status"], "white")),
            lot["owner_agent"],
            ", ".join(lot["assigned_subagents"]),
            lot["summary"],
        )
    return table


def make_validations_table(registry: dict) -> Table:
    table = Table(box=box.SIMPLE_HEAD, expand=True)
    table.add_column("Lot", style="bold dim", no_wrap=True)
    table.add_column("Validations", ratio=1)
    for lot in registry["lots"]:
        table.add_row(lot["id"], "\n".join(f"- {item}" for item in lot["validations"]))
    return table


def make_oss_table(registry: dict) -> Table:
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("Projet", style="bold green")
    table.add_column("Verdict", no_wrap=True)
    table.add_column("Cibles repo", ratio=1)
    for item in registry["oss_watch"]:
        table.add_row(item["name"], item["verdict"], ", ".join(item["mascarade_targets"]))
    return table


def make_logs_table(records: list[LogRecord]) -> Table:
    table = Table(box=box.SIMPLE_HEAD, expand=True)
    table.add_column("Fichier", ratio=1)
    table.add_column("Modifié", no_wrap=True)
    table.add_column("Taille", justify="right", no_wrap=True)
    for record in records[:20]:
        rel_path = record.path.relative_to(REPO_ROOT)
        table.add_row(str(rel_path), record.modified_at.strftime("%Y-%m-%d %H:%M"), _format_bytes(record.size_bytes))
    return table


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def build_layout(registry: dict, log_records: list[LogRecord]) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(Panel(Text("Mascarade Agent Ops Console", justify="center", style="bold cyan"), border_style="cyan"), size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(Layout(name="left"), Layout(name="right"))
    layout["left"].split_column(
        Layout(Panel(make_lots_table(registry), title="Lots actifs", border_style="cyan")),
        Layout(Panel(make_validations_table(registry), title="Validations", border_style="yellow")),
    )
    layout["right"].split_column(
        Layout(Panel(make_oss_table(registry), title="Veille OSS", border_style="green")),
        Layout(
            Panel(
                make_logs_table(log_records) if log_records else Text("Aucun log ancien a purger", style="dim"),
                title=f"Logs purgeables ({len(log_records)})",
                border_style="magenta",
            )
        ),
    )
    return layout


def export_markdown(registry: dict, log_records: list[LogRecord]) -> str:
    lines = ["# Mascarade Agent Ops Console", "", f"Plan: {registry['plan_id']}", ""]
    lines.append("## Lots actifs")
    for lot in registry["lots"]:
        lines.append(f"- **{lot['id']}** [{lot['priority']}] {lot['title']} — agent: {lot['owner_agent']}")
        lines.append(f"  - Sous-agents: {', '.join(lot['assigned_subagents'])}")
        lines.append(f"  - Compétences: {', '.join(lot['skills'])}")
        lines.append(f"  - Résumé: {lot['summary']}")
    lines.append("")
    lines.append("## Logs anciens")
    if not log_records:
        lines.append("- Aucun log purgeable")
    else:
        for record in log_records[:20]:
            rel_path = record.path.relative_to(REPO_ROOT)
            lines.append(f"- {rel_path} — {_format_bytes(record.size_bytes)} — {record.modified_at:%Y-%m-%d %H:%M}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mascarade Agent Ops Console")
    parser.add_argument("--export", choices=["markdown"], default=None)
    parser.add_argument("--purge-old-logs", action="store_true")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    registry = load_registry()
    log_policy = registry["log_policy"]
    log_records = scan_logs(log_policy["paths"], log_policy["purge_patterns"], args.days)

    if args.purge_old_logs:
        deleted = purge_logs(log_records)
        CONSOLE.print(f"[bold green]{deleted}[/bold green] logs supprimés")
        return

    if args.export == "markdown":
        print(export_markdown(registry, log_records))
        append_action_log("exported markdown report")
        return

    CONSOLE.print(build_layout(registry, log_records))
    append_action_log("rendered ops console")


if __name__ == "__main__":
    main()