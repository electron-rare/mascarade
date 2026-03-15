#!/usr/bin/env python3
"""Zellij TUI — manage remote zellij sessions across the P2P mesh.

Usage: python scripts/tools/zellij_tui.py
"""

import asyncio
import cmd
import sys

sys.path.insert(0, ".")
from mascarade.tools.zellij import ZellijAgent, NODES


class ZellijTUI(cmd.Cmd):
    intro = (
        "\n╔══════════════════════════════════════╗\n"
        "║     Mascarade Zellij Controller      ║\n"
        "╚══════════════════════════════════════╝\n"
        "\nNodes: " + ", ".join(f"{k} ({v['name']})" for k, v in NODES.items()) + "\n"
        "Type 'help' for commands.\n"
    )
    prompt = "zellij> "

    def __init__(self):
        super().__init__()
        self.agent = ZellijAgent()
        self.current_node = "tower"
        self.current_session = "mascarade"

    def _run(self, coro):
        return asyncio.run(coro)

    def do_node(self, arg):
        """Set current node: node <name>"""
        arg = arg.strip()
        if arg in NODES:
            self.current_node = arg
            print(f"  → Node set to: {arg} ({NODES[arg]['name']})")
        else:
            print(f"  Unknown node. Available: {', '.join(NODES.keys())}")

    def do_session(self, arg):
        """Set current session: session <name>"""
        arg = arg.strip()
        if arg:
            self.current_session = arg
            print(f"  → Session set to: {arg}")
        else:
            print(f"  Current session: {self.current_session}")

    def do_ls(self, arg):
        """List zellij sessions on current node"""
        node = arg.strip() or self.current_node
        print(f"  Scanning {node} ({NODES.get(node, {}).get('name', '?')})...")
        sessions = self._run(self.agent.list_sessions(node))
        if not sessions:
            print("  No sessions found.")
            return
        for s in sessions:
            status_icon = "●" if s.status == "active" else "○"
            print(f"  {status_icon} {s.name:30s} [{s.status:7s}] {s.created_ago}")

    def do_scan(self, _arg):
        """Scan all nodes for zellij sessions"""
        print("  Scanning all nodes...")
        for node_id in NODES:
            name = NODES[node_id]["name"]
            try:
                sessions = self._run(self.agent.list_sessions(node_id))
                if sessions:
                    print(f"\n  {name} ({node_id}):")
                    for s in sessions:
                        icon = "●" if s.status == "active" else "○"
                        print(f"    {icon} {s.name:30s} [{s.status}]")
                else:
                    print(f"\n  {name} ({node_id}): no sessions")
            except Exception as e:
                print(f"\n  {name} ({node_id}): error — {e}")

    def do_layout(self, arg):
        """Dump layout of current session"""
        session = arg.strip() or self.current_session
        print(f"  Dumping layout: {self.current_node}/{session}...")
        layout = self._run(self.agent.dump_layout(self.current_node, session))
        if layout.panes:
            print(f"\n  Panes ({len(layout.panes)}):")
            for p in layout.panes:
                focus = " [FOCUS]" if p.is_focused else ""
                print(f"    #{p.pane_id}: {p.command}{focus}")
        else:
            print("  No panes found in layout.")
        if "--raw" in (arg or ""):
            print(f"\n  Raw layout:\n{layout.raw_layout}")

    def do_send(self, arg):
        """Send text to current session pane: send <text>"""
        if not arg.strip():
            print("  Usage: send <text>")
            return
        ok = self._run(self.agent.send_to_pane(self.current_node, self.current_session, arg.strip()))
        if ok:
            print(f"  ✓ Sent to {self.current_node}/{self.current_session}")
        else:
            print(f"  ✗ Failed to send")

    def do_enter(self, _arg):
        """Send Enter key to current session pane"""
        ok = self._run(self.agent.send_enter(self.current_node, self.current_session))
        print("  ✓ Enter sent" if ok else "  ✗ Failed")

    def do_run(self, arg):
        """Send command + Enter: run <command>"""
        if not arg.strip():
            print("  Usage: run <command>")
            return
        ok1 = self._run(self.agent.send_to_pane(self.current_node, self.current_session, arg.strip()))
        ok2 = self._run(self.agent.send_enter(self.current_node, self.current_session))
        if ok1 and ok2:
            print(f"  ✓ Ran on {self.current_node}/{self.current_session}: {arg.strip()}")
        else:
            print(f"  ✗ Failed")

    def do_kill(self, arg):
        """Kill a session: kill [session_name]"""
        session = arg.strip() or self.current_session
        confirm = input(f"  Kill {self.current_node}/{session}? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return
        ok = self._run(self.agent.kill_session(self.current_node, session))
        print("  ✓ Killed" if ok else "  ✗ Failed")

    def do_status(self, _arg):
        """Show current node/session selection"""
        print(f"  Node:    {self.current_node} ({NODES.get(self.current_node, {}).get('name', '?')})")
        print(f"  Session: {self.current_session}")

    def do_quit(self, _arg):
        """Exit"""
        print("  Bye.")
        return True

    do_q = do_quit
    do_exit = do_quit


if __name__ == "__main__":
    try:
        ZellijTUI().cmdloop()
    except KeyboardInterrupt:
        print("\n  Bye.")
