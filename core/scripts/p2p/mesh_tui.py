#!/usr/bin/env python3
"""P2P Mesh TUI — interactive terminal dashboard for the mascarade mesh.

Usage:
    python scripts/p2p/mesh_tui.py
"""

import os
import subprocess
import time

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

NODES = {
    "VM (bootstrap)": {
        "ssh": "root@192.168.0.119",
        "port": 4001,
        "role": "infra",
        "caps": ["docker", "p2p-relay", "compute"],
    },
    "GrosMac (bridge)": {
        "ssh": None,  # local
        "port": 4001,
        "role": "bridge",
        "caps": [
            "p2p-relay",
            "p2p-bridge",
            "llm-inference",
            "ft-research",
            "ft-dataset",
            "ft-teacher",
            "ft-archive",
        ],
    },
    "CILS": {
        "ssh": "cils@192.168.0.210",
        "port": 4001,
        "role": "worker",
        "caps": ["compute", "ft-validation"],
    },
    "Tower": {
        "ssh": "clems@192.168.0.120",
        "port": 4001,
        "role": "worker",
        "caps": ["compute", "storage", "ft-archive"],
    },
    "KXKM-AI": {
        "ssh": "kxkm@kxkm-ai",
        "port": 4001,
        "role": "worker",
        "caps": [
            "llm-inference",
            "gpu",
            "compute",
            "ft-student",
            "ft-analysis",
            "ft-reinforcement",
        ],
    },
}


def header(text):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}\n")


def check_node(name, info):
    """Check if a node is up by testing SSH + port."""
    ssh = info["ssh"]
    port = info["port"]

    if ssh is None:
        # Local
        ret = os.system(f"lsof -ti:{port} >/dev/null 2>&1")
        return ret == 0

    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=3",
                "-o",
                "BatchMode=yes",
                ssh,
                f"lsof -ti:{port} 2>/dev/null || ss -tlnp 2>/dev/null | grep :{port}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except Exception:
        return False


def show_mesh_status():
    header("MESH STATUS")
    print(f"  {'Node':22s} {'Role':8s} {'Port':6s} {'Status':10s} Capabilities")
    print(f"  {'─'*22} {'─'*8} {'─'*6} {'─'*10} {'─'*30}")

    for name, info in NODES.items():
        up = check_node(name, info)
        status = f"{GREEN}UP{RESET}" if up else f"{RED}DOWN{RESET}"
        caps = ", ".join(info["caps"])
        role = info["role"]
        port = str(info["port"])
        print(f"  {BOLD}{name:22s}{RESET} {role:8s} :{port:<5s} {status:>20s}  {DIM}{caps}{RESET}")


def show_node_detail(name, info):
    header(f"NODE: {name}")
    ssh = info["ssh"]

    if ssh is None:
        print(f"  {DIM}Local node{RESET}")
        try:
            result = subprocess.run(
                ["uname", "-m"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            print(f"  {BOLD}{'Arch':12s}{RESET} {result.stdout.strip()}")
            result = subprocess.run(
                ["sw_vers", "--productVersion"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                print(f"  {BOLD}{'macOS':12s}{RESET} {result.stdout.strip()}")
        except Exception:
            pass
        return

    commands = {
        "OS": "uname -sr",
        "CPU": "nproc",
        "RAM": "free -h 2>/dev/null | head -2 || vm_stat 2>/dev/null | head -5",
        "GPU": "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'No GPU'",
        "Disk": "df -h / 2>/dev/null | tail -1",
        "Python": "python3 --version 2>&1",
        "P2P port": f"lsof -ti:{info['port']} 2>/dev/null && echo 'listening' || echo 'not listening'",
    }

    for label, cmd in commands.items():
        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", ssh, cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout.strip()[:80]
            print(f"  {BOLD}{label:12s}{RESET} {output}")
        except Exception as e:
            print(f"  {BOLD}{label:12s}{RESET} {RED}error: {e}{RESET}")


def start_node(name, info):
    ssh = info["ssh"]
    if ssh is None:
        print(f"  {YELLOW}Use run_all.sh to start local nodes{RESET}")
        return

    print(f"  {DIM}Starting {name}...{RESET}")
    # Build the start command based on node type
    if "bootstrap" in name.lower():
        cmd = "cd ~/mascarade/core && nohup python3 scripts/p2p/node_start_bootstrap.py > /tmp/p2p.log 2>&1 &"
    else:
        caps = ",".join(info["caps"])
        cmd = (
            f"cd ~/mascarade/core && "
            f"P2P_CAPABILITIES={caps} P2P_BOOTSTRAP_PORT=4001 "
            f"nohup python3 scripts/p2p/task_handler_worker.py > /tmp/p2p.log 2>&1 &"
        )

    try:
        subprocess.run(["ssh", ssh, cmd], timeout=10)
        time.sleep(1)
        up = check_node(name, info)
        if up:
            print(f"  {GREEN}✓ {name} started{RESET}")
        else:
            print(f"  {YELLOW}⚠ Started but not yet listening{RESET}")
    except Exception as e:
        print(f"  {RED}✗ Failed: {e}{RESET}")


def stop_node(name, info):
    ssh = info["ssh"]
    port = info["port"]
    if ssh is None:
        print(f"  {YELLOW}Use run_all.sh to stop local nodes{RESET}")
        return

    print(f"  {DIM}Stopping {name}...{RESET}")
    try:
        subprocess.run(
            ["ssh", ssh, f"lsof -ti:{port} | xargs kill 2>/dev/null; echo done"],
            timeout=10,
        )
        print(f"  {GREEN}✓ {name} stopped{RESET}")
    except Exception as e:
        print(f"  {RED}✗ Failed: {e}{RESET}")


def main_menu():
    options = [
        "Status mesh complet",
        "Détail nœud",
        "Démarrer nœud",
        "Arrêter nœud",
        "Démarrer tous les nœuds",
        "Arrêter tous les nœuds",
    ]

    while True:
        header("MASCARADE MESH TUI")
        for i, opt in enumerate(options, 1):
            print(f"  {BOLD}{i}{RESET}. {opt}")
        print(f"  {BOLD}0{RESET}. Quitter")

        try:
            choice = input("\n  Choix > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice in ("0", "q", "quit"):
            break
        elif choice == "1":
            show_mesh_status()
        elif choice == "2":
            header("CHOISIR NŒUD")
            names = list(NODES.keys())
            for i, n in enumerate(names, 1):
                print(f"  {BOLD}{i}{RESET}. {n}")
            try:
                idx = int(input("\n  Nœud > ").strip()) - 1
                if 0 <= idx < len(names):
                    show_node_detail(names[idx], NODES[names[idx]])
            except (ValueError, EOFError):
                pass
        elif choice == "3":
            header("DÉMARRER NŒUD")
            names = list(NODES.keys())
            for i, n in enumerate(names, 1):
                print(f"  {BOLD}{i}{RESET}. {n}")
            try:
                idx = int(input("\n  Nœud > ").strip()) - 1
                if 0 <= idx < len(names):
                    start_node(names[idx], NODES[names[idx]])
            except (ValueError, EOFError):
                pass
        elif choice == "4":
            header("ARRÊTER NŒUD")
            names = list(NODES.keys())
            for i, n in enumerate(names, 1):
                print(f"  {BOLD}{i}{RESET}. {n}")
            try:
                idx = int(input("\n  Nœud > ").strip()) - 1
                if 0 <= idx < len(names):
                    stop_node(names[idx], NODES[names[idx]])
            except (ValueError, EOFError):
                pass
        elif choice == "5":
            header("DÉMARRAGE COMPLET")
            for name, info in NODES.items():
                start_node(name, info)
        elif choice == "6":
            header("ARRÊT COMPLET")
            for name, info in NODES.items():
                stop_node(name, info)


if __name__ == "__main__":
    main_menu()
