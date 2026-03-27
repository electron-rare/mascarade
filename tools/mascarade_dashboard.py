#!/usr/bin/env python3
"""
MASCARADE MESH DASHBOARD
========================
Single-file TUI dashboard for monitoring the mascarade mesh infrastructure.
Shows machine status, git repos, Ollama models, Docker health, and services.

Usage:
    python mascarade_dashboard.py              # Live refresh every 30s
    python mascarade_dashboard.py --interval 10 # Refresh every 10s
    python mascarade_dashboard.py --once        # Single run then exit
"""

import argparse
import asyncio
import datetime
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOG_FILE = "/tmp/mascarade_dashboard.log"
SSH_TIMEOUT = 15  # seconds

MACHINES = {
    "GrosMac": {"host": "localhost", "ssh": None, "type": "local"},
    "VM": {"host": "192.168.0.119", "ssh": "root@192.168.0.119", "type": "docker"},
    "Tower": {"host": "192.168.0.120", "ssh": "clems@192.168.0.120", "type": "docker"},
    "CILS": {"host": "192.168.0.210", "ssh": "cils@192.168.0.210", "type": "worker"},
    "KXKM-AI": {"host": "kxkm-ai", "ssh": "kxkm@kxkm-ai", "type": "gpu"},
}

REPOS = {
    "mascarade": "/Users/electron/Documents/Projets/mascarade",
    "mascarade-vol": "/Volumes/root/mascarade-main",
    "Zacus": "/Users/electron/Documents/Projets_Creatifs/le-mystere-professeur-zacus",
    "Kill_LIFE": "/Users/electron/Kill_LIFE",
    "crazy_life": "/Users/electron/crazy_life",
}

# Services to probe per machine (name, check command, port)
SERVICES = {
    "GrosMac": [
        ("mascarade-bridge", "curl -sf http://localhost:4001/health", 4001),
    ],
    "VM": [
        ("mascarade-api", "curl -sf http://localhost:8100/health", 8100),
        ("p2p-bootstrap", "curl -sf http://localhost:4002/health", 4002),
    ],
    "Tower": [
        ("mascarade-core", "curl -sf http://localhost:8100/health", 8100),
        ("ollama", "curl -sf http://localhost:11434/api/tags", 11434),
        ("piper-tts", "curl -sf http://localhost:8001/", 8001),
        ("openai-proxy", "curl -sf http://localhost:8901/health", 8901),
        ("nextcloud", "curl -sf http://localhost:8880/status.php", 8880),
    ],
    "CILS": [
        ("mascarade-core", "curl -sf http://localhost:8100/health", 8100),
        ("ollama", "curl -sf http://localhost:11434/api/tags", 11434),
        ("p2p-worker", "curl -sf http://localhost:4001/health", 4001),
    ],
    "KXKM-AI": [
        ("ollama", "curl -sf http://localhost:11434/api/tags", 11434),
        ("p2p-worker", "curl -sf http://localhost:4001/health", 4001),
    ],
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("dashboard")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MachineStatus:
    name: str
    reachable: bool = False
    load: str = "-"
    ram: str = "-"
    docker_count: int = 0
    gpu: str = "-"
    uptime: str = "-"


@dataclass
class RepoStatus:
    name: str
    path: str
    exists: bool = False
    branch: str = "-"
    ahead: int = 0
    behind: int = 0
    dirty: int = 0


@dataclass
class OllamaModel:
    machine: str
    name: str
    size: str


@dataclass
class ServiceStatus:
    name: str
    machine: str
    status: str = "UNKNOWN"
    port: int = 0


# ---------------------------------------------------------------------------
# Async command execution
# ---------------------------------------------------------------------------

async def run_local(cmd: str, timeout: int = SSH_TIMEOUT) -> tuple[bool, str]:
    """Run a local shell command with timeout."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        ok = proc.returncode == 0
        return ok, stdout.decode("utf-8", errors="replace").strip()
    except asyncio.TimeoutError:
        log.warning("Local command timed out: %s", cmd)
        return False, ""
    except Exception as e:
        log.warning("Local command failed: %s — %s", cmd, e)
        return False, ""


async def run_ssh(ssh_target: str, cmd: str, timeout: int = SSH_TIMEOUT) -> tuple[bool, str]:
    """Run a command on a remote machine via SSH."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-o", "ConnectTimeout=8",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            ssh_target,
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        ok = proc.returncode == 0
        return ok, stdout.decode("utf-8", errors="replace").strip()
    except asyncio.TimeoutError:
        log.warning("SSH timed out: %s -> %s", ssh_target, cmd)
        return False, ""
    except Exception as e:
        log.warning("SSH failed: %s -> %s — %s", ssh_target, cmd, e)
        return False, ""


async def run_on(machine_name: str, cmd: str, timeout: int = SSH_TIMEOUT) -> tuple[bool, str]:
    """Run a command on the given machine (local or SSH)."""
    cfg = MACHINES[machine_name]
    if cfg["ssh"] is None:
        return await run_local(cmd, timeout)
    return await run_ssh(cfg["ssh"], cmd, timeout)


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

async def collect_machine(name: str) -> MachineStatus:
    """Collect status for one machine."""
    ms = MachineStatus(name=name)
    cfg = MACHINES[name]

    # Ping / reachability + uptime
    ok, out = await run_on(name, "uptime")
    if not ok:
        log.info("Machine %s: UNREACHABLE", name)
        return ms

    ms.reachable = True
    # Parse uptime for load average
    if "load average" in out:
        ms.load = out.split("load average:")[-1].strip().split(",")[0].strip()
    # Parse uptime string
    if "up" in out:
        parts = out.split("up")[1].split(",")
        # Take first 1-2 parts as uptime
        up_str = parts[0].strip()
        if len(parts) > 1 and "user" not in parts[1]:
            up_str += ", " + parts[1].strip()
        ms.uptime = up_str

    # RAM
    if cfg["type"] == "local":
        # macOS: use sysctl for total and vm_stat for used
        ok, out = await run_on(name, "sysctl -n hw.memsize 2>/dev/null")
        if ok and out:
            total_gb = int(out) / (1024**3)
            ok2, out2 = await run_on(name, "vm_stat 2>/dev/null")
            if ok2 and out2:
                # Parse page size and active+wired pages
                page_size = 16384  # default
                ps_match = re.search(r'page size of (\d+) bytes', out2)
                if ps_match:
                    page_size = int(ps_match.group(1))
                active = wired = compressed = 0
                for line in out2.splitlines():
                    if 'Pages active:' in line:
                        active = int(line.split(':')[1].strip().rstrip('.'))
                    elif 'Pages wired' in line:
                        wired = int(line.split(':')[1].strip().rstrip('.'))
                    elif 'Pages occupied by compressor:' in line:
                        compressed = int(line.split(':')[1].strip().rstrip('.'))
                used_gb = (active + wired + compressed) * page_size / (1024**3)
                ms.ram = f"{used_gb:.1f}Gi/{total_gb:.0f}Gi"
            else:
                ms.ram = f"~/{total_gb:.0f}Gi"
    else:
        ok, out = await run_on(name, "free -h 2>/dev/null | awk '/^Mem:/{print $3\"/\"$2}'")
        if ok and out and "/" in out:
            ms.ram = out

    # Docker count
    if cfg["type"] in ("docker", "local"):
        ok, out = await run_on(name, "docker ps -q 2>/dev/null | wc -l")
        if ok and out.strip():
            try:
                ms.docker_count = int(out.strip())
            except ValueError:
                pass

    # GPU (KXKM-AI)
    if cfg["type"] == "gpu":
        ok, out = await run_on(name, "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null")
        if ok and out:
            parts = out.split(",")
            if len(parts) >= 4:
                gpu_name = parts[0].strip()
                gpu_util = parts[1].strip()
                mem_used = parts[2].strip()
                mem_total = parts[3].strip()
                ms.gpu = f"{gpu_name} {gpu_util}% {mem_used}/{mem_total}MiB"

    log.info("Machine %s: reachable=%s load=%s ram=%s docker=%d",
             name, ms.reachable, ms.load, ms.ram, ms.docker_count)
    return ms


async def collect_repo(name: str, path: str) -> RepoStatus:
    """Collect git status for one repo."""
    rs = RepoStatus(name=name, path=path)

    if not Path(path).is_dir():
        log.info("Repo %s: path not found (%s)", name, path)
        return rs

    rs.exists = True

    # Branch
    ok, out = await run_local(f"git -C {path} rev-parse --abbrev-ref HEAD 2>/dev/null")
    if ok:
        rs.branch = out

    # Ahead/behind
    ok, out = await run_local(
        f"git -C {path} rev-list --left-right --count HEAD...@{{upstream}} 2>/dev/null"
    )
    if ok and out:
        parts = out.split()
        if len(parts) == 2:
            try:
                rs.ahead = int(parts[0])
                rs.behind = int(parts[1])
            except ValueError:
                pass

    # Dirty files
    ok, out = await run_local(f"git -C {path} status --porcelain 2>/dev/null | wc -l")
    if ok and out.strip():
        try:
            rs.dirty = int(out.strip())
        except ValueError:
            pass

    log.info("Repo %s: branch=%s ahead=%d behind=%d dirty=%d",
             name, rs.branch, rs.ahead, rs.behind, rs.dirty)
    return rs


async def collect_ollama(machine_name: str) -> list[OllamaModel]:
    """Collect Ollama models from a machine."""
    models = []
    ok, out = await run_on(machine_name, "curl -sf http://localhost:11434/api/tags 2>/dev/null")
    if not ok or not out:
        return models

    try:
        data = json.loads(out)
        for m in data.get("models", []):
            name = m.get("name", "?")
            size_bytes = m.get("size", 0)
            if size_bytes > 1_000_000_000:
                size_str = f"{size_bytes / 1_000_000_000:.1f}GB"
            elif size_bytes > 1_000_000:
                size_str = f"{size_bytes / 1_000_000:.0f}MB"
            else:
                size_str = f"{size_bytes}B"
            models.append(OllamaModel(machine=machine_name, name=name, size=size_str))
    except (json.JSONDecodeError, KeyError) as e:
        log.warning("Ollama JSON parse error on %s: %s", machine_name, e)

    log.info("Ollama %s: %d models", machine_name, len(models))
    return models


async def collect_service(machine_name: str, svc_name: str, check_cmd: str, port: int) -> ServiceStatus:
    """Check one service on a machine."""
    ss = ServiceStatus(name=svc_name, machine=machine_name, port=port)
    ok, _ = await run_on(machine_name, check_cmd)
    ss.status = "UP" if ok else "DOWN"
    log.info("Service %s@%s: %s", svc_name, machine_name, ss.status)
    return ss


# ---------------------------------------------------------------------------
# Full collection
# ---------------------------------------------------------------------------

async def collect_all() -> dict:
    """Run all probes in parallel and return structured results."""
    tasks = {}

    # Machines
    machine_tasks = {name: asyncio.create_task(collect_machine(name)) for name in MACHINES}

    # Repos
    repo_tasks = {name: asyncio.create_task(collect_repo(name, path)) for name, path in REPOS.items()}

    # Ollama — only on machines that might run it
    ollama_machines = ["Tower", "CILS", "KXKM-AI"]
    ollama_tasks = {name: asyncio.create_task(collect_ollama(name)) for name in ollama_machines}

    # Services
    svc_tasks = []
    for machine_name, svcs in SERVICES.items():
        for svc_name, check_cmd, port in svcs:
            svc_tasks.append(asyncio.create_task(
                collect_service(machine_name, svc_name, check_cmd, port)
            ))

    # Await all
    machines = {name: await t for name, t in machine_tasks.items()}
    repos = {name: await t for name, t in repo_tasks.items()}

    ollama_models = []
    for name, t in ollama_tasks.items():
        ollama_models.extend(await t)

    services = [await t for t in svc_tasks]

    return {
        "machines": machines,
        "repos": repos,
        "ollama": ollama_models,
        "services": services,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

TYPE_ICONS = {
    "local": "[bold cyan]LOCAL[/]",
    "docker": "[bold blue]DOCKER[/]",
    "worker": "[bold yellow]WORKER[/]",
    "gpu": "[bold magenta]GPU[/]",
}


def render_header(timestamp: str) -> Panel:
    title = Text("MASCARADE MESH DASHBOARD", style="bold white on blue", justify="center")
    sub = Text(f"Last refresh: {timestamp}", style="dim", justify="center")
    content = Text.assemble(title, "\n", sub)
    return Panel(content, style="blue", padding=(0, 2))


def render_machines(machines: dict[str, MachineStatus]) -> Panel:
    table = Table(expand=True, show_lines=False, pad_edge=True)
    table.add_column("Machine", style="bold", min_width=10, overflow="fold")
    table.add_column("Type", min_width=8, overflow="fold")
    table.add_column("Status", min_width=12, overflow="fold")
    table.add_column("Load", min_width=6, overflow="fold")
    table.add_column("RAM", min_width=12, overflow="fold")
    table.add_column("Docker", justify="right", min_width=7, overflow="fold")
    table.add_column("GPU", min_width=20, overflow="fold", no_wrap=False)
    table.add_column("Uptime", min_width=14, overflow="fold", no_wrap=False)

    for name, ms in machines.items():
        cfg = MACHINES[name]
        status = "[bold green]OK[/]" if ms.reachable else "[bold red]UNREACHABLE[/]"
        type_label = TYPE_ICONS.get(cfg["type"], cfg["type"])
        docker_str = str(ms.docker_count) if ms.docker_count else "-"
        gpu_str = ms.gpu if ms.gpu != "-" else ""
        table.add_row(
            name, type_label, status, ms.load, ms.ram,
            docker_str, gpu_str, ms.uptime,
        )

    return Panel(table, title="[bold]Machines[/]", border_style="cyan")


def render_repos(repos: dict[str, RepoStatus]) -> Panel:
    table = Table(expand=True, show_lines=False)
    table.add_column("Repo", style="bold", min_width=14, overflow="fold")
    table.add_column("Branch", min_width=20, overflow="fold", no_wrap=False)
    table.add_column("Ahead", justify="right", min_width=6, overflow="fold")
    table.add_column("Behind", justify="right", min_width=7, overflow="fold")
    table.add_column("Dirty", justify="right", min_width=6, overflow="fold")
    table.add_column("Path", style="dim", min_width=20, overflow="fold", no_wrap=False)

    for name, rs in repos.items():
        if not rs.exists:
            table.add_row(name, "[dim]NOT FOUND[/]", "-", "-", "-", rs.path)
            continue

        branch_style = "green" if rs.branch in ("main", "master") else "yellow"
        ahead_str = f"[green]+{rs.ahead}[/]" if rs.ahead else "0"
        behind_str = f"[red]-{rs.behind}[/]" if rs.behind else "0"
        dirty_str = f"[red]{rs.dirty}[/]" if rs.dirty else "[green]0[/]"
        table.add_row(
            name, f"[{branch_style}]{rs.branch}[/]",
            ahead_str, behind_str, dirty_str, rs.path,
        )

    return Panel(table, title="[bold]Git Repositories[/]", border_style="green")


def render_ollama(models: list[OllamaModel]) -> Panel:
    table = Table(expand=True, show_lines=False)
    table.add_column("Machine", style="bold", min_width=10, overflow="fold")
    table.add_column("Model", min_width=20, overflow="fold", no_wrap=False)
    table.add_column("Size", justify="right", min_width=8, overflow="fold")

    if not models:
        table.add_row("[dim]No models found[/]", "", "")
    else:
        # Sort by machine then model name
        for m in sorted(models, key=lambda x: (x.machine, x.name)):
            table.add_row(m.machine, m.name, m.size)

    return Panel(table, title="[bold]Ollama Models[/]", border_style="yellow")


def render_services(services: list[ServiceStatus]) -> Panel:
    table = Table(expand=True, show_lines=False)
    table.add_column("Service", style="bold", min_width=18, overflow="fold")
    table.add_column("Machine", min_width=10, overflow="fold")
    table.add_column("Port", justify="right", min_width=6, overflow="fold")
    table.add_column("Status", min_width=8, overflow="fold")

    for ss in sorted(services, key=lambda x: (x.machine, x.name)):
        status_str = "[bold green]UP[/]" if ss.status == "UP" else "[bold red]DOWN[/]"
        table.add_row(ss.name, ss.machine, str(ss.port), status_str)

    return Panel(table, title="[bold]Services[/]", border_style="magenta")


def render_footer(interval: int, countdown: int) -> Panel:
    text = Text.assemble(
        ("Log: ", "dim"),
        (LOG_FILE, "bold"),
        ("  |  ", "dim"),
        (f"Refresh in {countdown}s (interval={interval}s)", "dim"),
        ("  |  ", "dim"),
        ("Ctrl+C to quit", "dim italic"),
    )
    return Panel(text, style="dim")


def build_display(data: dict, interval: int, countdown: int) -> Layout:
    """Build the full dashboard layout."""
    layout = Layout()

    layout.split_column(
        Layout(render_header(data["timestamp"]), name="header", size=4),
        Layout(render_machines(data["machines"]), name="machines", size=len(MACHINES) + 4),
        Layout(render_repos(data["repos"]), name="repos", size=len(REPOS) + 4),
        Layout(name="bottom"),
        Layout(render_footer(interval, countdown), name="footer", size=3),
    )

    # Split bottom into ollama + services side by side
    layout["bottom"].split_row(
        Layout(render_ollama(data["ollama"]), name="ollama"),
        Layout(render_services(data["services"]), name="services"),
    )

    return layout


def build_display_static(data: dict) -> Layout:
    """Build layout for --once mode (no countdown)."""
    return build_display(data, 0, 0)


# ---------------------------------------------------------------------------
# Main loops
# ---------------------------------------------------------------------------

async def run_once():
    """Single collection + render, then exit."""
    console = Console(width=max(160, os.get_terminal_size(0).columns) if sys.stdout.isatty() else 160)
    log.info("=== Dashboard run (once mode) ===")
    data = await collect_all()
    layout = build_display_static(data)
    console.print(layout)
    log.info("=== Done ===")


async def run_live(interval: int):
    """Live dashboard with periodic refresh."""
    console = Console(width=max(160, os.get_terminal_size(0).columns) if sys.stdout.isatty() else 160)
    log.info("=== Dashboard started (interval=%ds) ===", interval)

    # Graceful shutdown
    stop_event = asyncio.Event()

    def handle_signal(*_):
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    data = {"machines": {}, "repos": {}, "ollama": [], "services": [], "timestamp": "loading..."}

    with Live(build_display(data, interval, interval), console=console, refresh_per_second=1, screen=True) as live:
        while not stop_event.is_set():
            # Collect
            data = await collect_all()
            countdown = interval

            # Countdown loop
            while countdown > 0 and not stop_event.is_set():
                live.update(build_display(data, interval, countdown))
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass
                countdown -= 1

    log.info("=== Dashboard stopped ===")
    console.print("\n[dim]Dashboard stopped.[/]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MASCARADE MESH DASHBOARD - Monitor all infrastructure nodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                  Live dashboard, refresh every 30s
  %(prog)s --interval 10    Live dashboard, refresh every 10s
  %(prog)s --once           Single run, print and exit
        """,
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Refresh interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run once and exit (useful for CI/cron)",
    )
    args = parser.parse_args()

    if args.once:
        asyncio.run(run_once())
    else:
        asyncio.run(run_live(args.interval))


if __name__ == "__main__":
    main()
