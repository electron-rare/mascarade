"""Zellij remote session agent — pilot zellij sessions on P2P mesh nodes.

Provides async tools to:
- List sessions on remote nodes
- Dump layout of a session
- Send commands to panes
- Create new sessions with custom layouts
- Read pane output (scrollback)

Works via SSH + zellij CLI actions.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.tools.zellij")

# Known nodes with SSH access
NODES = {
    "tower": {"host": "clems@192.168.0.120", "name": "Tower"},
    "cils": {"host": "cils@192.168.0.210", "name": "CILS MacBook"},
    "vm": {"host": "root@192.168.0.119", "name": "VM GPU"},
    "kxkm": {"host": "kxkm@kxkm-ai", "name": "KXKM-AI"},
    "local": {"host": None, "name": "GrosMac (local)"},
}


@dataclass
class ZellijSession:
    name: str
    node: str
    status: str  # "active", "exited"
    created_ago: str = ""


@dataclass
class ZellijPane:
    pane_id: int
    command: str
    is_focused: bool = False
    title: str = ""


@dataclass
class ZellijLayout:
    session: str
    node: str
    panes: list[ZellijPane] = field(default_factory=list)
    raw_layout: str = ""


class ZellijAgent:
    """Remote zellij session manager across P2P mesh nodes."""

    def __init__(self, *, ssh_timeout: int = 10):
        self.ssh_timeout = ssh_timeout

    async def _ssh_cmd(self, node: str, cmd: str) -> tuple[str, int]:
        """Execute a command on a remote node via SSH."""
        node_info = NODES.get(node)
        if not node_info:
            return f"Unknown node: {node}", 1

        host = node_info["host"]
        if host is None:
            # Local execution
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.ssh_timeout
            )
            output = stdout.decode() + stderr.decode()
            return output.strip(), proc.returncode or 0

        ssh_cmd = f"ssh -o ConnectTimeout={self.ssh_timeout} -o StrictHostKeyChecking=no {host} {cmd!r}"
        proc = await asyncio.create_subprocess_shell(
            ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=self.ssh_timeout + 5
        )
        output = stdout.decode() + stderr.decode()
        return output.strip(), proc.returncode or 0

    async def list_sessions(self, node: str = "tower") -> list[ZellijSession]:
        """List all zellij sessions on a node."""
        output, rc = await self._ssh_cmd(node, "zellij list-sessions 2>&1")
        if rc != 0:
            logger.warning("Failed to list sessions on %s: %s", node, output)
            return []

        sessions = []
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Parse: "session-name [Created Xh ago] (EXITED - attach to resurrect)"
            # Remove ANSI codes
            import re

            clean = re.sub(r"\x1b\[[0-9;]*m", "", line)
            parts = clean.split()
            if not parts:
                continue
            name = parts[0]
            status = "exited" if "EXITED" in clean else "active"
            created = ""
            if "Created" in clean:
                try:
                    start = clean.index("Created") + 8
                    end = clean.index("ago", start) + 3
                    created = clean[start:end].strip()
                except ValueError:
                    pass
            sessions.append(
                ZellijSession(
                    name=name,
                    node=node,
                    status=status,
                    created_ago=created,
                )
            )

        logger.info("Found %d sessions on %s", len(sessions), node)
        return sessions

    async def dump_layout(
        self, node: str = "tower", session: str = "mascarade"
    ) -> ZellijLayout:
        """Dump the layout of a zellij session."""
        output, rc = await self._ssh_cmd(
            node, f"zellij -s {session} action dump-layout 2>&1"
        )
        if rc != 0:
            return ZellijLayout(
                session=session, node=node, raw_layout=f"Error: {output}"
            )

        # Parse panes from layout
        panes = []
        import re

        for match in re.finditer(r'pane command="([^"]+)"', output):
            cmd = match.group(1)
            panes.append(ZellijPane(pane_id=len(panes), command=cmd))

        return ZellijLayout(
            session=session,
            node=node,
            panes=panes,
            raw_layout=output,
        )

    async def send_to_pane(
        self,
        node: str,
        session: str,
        text: str,
        *,
        pane_index: int = 0,
    ) -> bool:
        """Send text input to a specific pane in a zellij session."""
        # Write bytes to the focused pane
        escaped = text.replace("'", "'\\''")
        cmd = f"zellij -s {session} action write-chars '{escaped}'"
        output, rc = await self._ssh_cmd(node, cmd)
        if rc != 0:
            logger.warning(
                "Failed to write to pane on %s/%s: %s", node, session, output
            )
            return False
        logger.info("Sent %d chars to %s/%s", len(text), node, session)
        return True

    async def send_enter(self, node: str, session: str) -> bool:
        """Send Enter key to the focused pane."""
        cmd = f"zellij -s {session} action write 10"
        _, rc = await self._ssh_cmd(node, cmd)
        return rc == 0

    async def new_session(
        self,
        node: str,
        session: str,
        *,
        layout: str | None = None,
    ) -> bool:
        """Create a new zellij session on a node."""
        layout_arg = f"--layout {layout}" if layout else ""
        cmd = f"zellij -s {session} {layout_arg} &"
        _, rc = await self._ssh_cmd(node, f"nohup {cmd} > /dev/null 2>&1")
        return rc == 0

    async def kill_session(self, node: str, session: str) -> bool:
        """Kill a zellij session."""
        cmd = f"zellij kill-session {session}"
        _, rc = await self._ssh_cmd(node, cmd)
        return rc == 0

    async def scan_all_nodes(self) -> dict[str, list[ZellijSession]]:
        """Scan all known nodes for zellij sessions."""
        results = {}
        tasks = []
        for node_id in NODES:
            tasks.append((node_id, self.list_sessions(node_id)))

        for node_id, task in tasks:
            try:
                sessions = await task
                if sessions:
                    results[node_id] = sessions
            except Exception as e:
                logger.warning("Failed to scan %s: %s", node_id, e)

        return results
