"""CLI coding agents — Vibe, Codex, Claude Code integration.

Wraps external CLI coding assistants as mascarade agents, enabling
orchestration of Vibe (Mistral), Codex (OpenAI), and Claude Code
(Anthropic) from the mascarade platform.

Each agent spawns the CLI in programmatic mode, parses the output,
and returns structured LLMResponse objects.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any

from mascarade.agents.base import Agent
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy

logger = logging.getLogger("mascarade.agents.cli")

# Default timeouts (seconds)
_DEFAULT_TIMEOUT = 300
_DEFAULT_MAX_TURNS = 20


# ---------------------------------------------------------------------------
# Shared CLI execution helpers
# ---------------------------------------------------------------------------


async def _run_cli(
    cmd: list[str],
    *,
    workdir: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Run a CLI command and return (stdout, stderr, returncode)."""
    import os

    run_env = {**os.environ, **(env or {})}
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
        env=run_env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"CLI command timed out after {timeout}s: {' '.join(cmd)}") from None

    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        proc.returncode or 0,
    )


def _cli_available(binary: str) -> bool:
    """Check if a CLI binary is available in PATH."""
    return shutil.which(binary) is not None


# ---------------------------------------------------------------------------
# Mistral Vibe Agent
# ---------------------------------------------------------------------------


class VibeAgent(Agent):
    """Mistral Vibe CLI coding agent.

    Uses `vibe --prompt "..." --output json --auto-approve` for programmatic
    execution. Supports max_turns and max_price limits.
    """

    def __init__(
        self,
        max_turns: int = _DEFAULT_MAX_TURNS,
        max_price: float = 2.0,
        workdir: str | None = None,
    ):
        super().__init__(
            name="vibe",
            description="Mistral Vibe — agent de code CLI pour génération, refactoring, debugging (Mistral/Devstral)",
            system_prompt=(
                "You are the Vibe CLI agent powered by Mistral. "
                "Execute coding tasks: write, refactor, debug, test. "
                "Use tools available: read_file, write_file, bash, grep, search_replace."
            ),
            preferred_provider="codestral",
            strategy=Strategy.SPECIFIC,
            temperature=0.2,
            max_tokens=8192,
        )
        self._max_turns = max_turns
        self._max_price = max_price
        self._workdir = workdir

    @property
    def is_available(self) -> bool:
        return _cli_available("vibe")

    async def run(
        self,
        prompt: str,
        *,
        router: Router | None = None,
        context: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Execute Vibe in programmatic mode."""
        if not self.is_available:
            raise RuntimeError(
                "vibe CLI not found. Install: curl -LsSf https://mistral.ai/vibe/install.sh | bash"
            )

        cmd = [
            "vibe",
            "--prompt",
            prompt,
            "--output",
            "json",
            "--max-turns",
            str(self._max_turns),
            "--max-price",
            str(self._max_price),
        ]
        if self._workdir:
            cmd.extend(["--workdir", self._workdir])

        stdout, stderr, code = await _run_cli(cmd, workdir=self._workdir)

        # Parse JSON output
        content = stdout.strip()
        try:
            data = json.loads(content)
            result_text = data.get("result", {}).get("text", content)
            usage = {
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
            }
            model = data.get("model", "devstral-small-2505")
        except (json.JSONDecodeError, KeyError):
            result_text = content or stderr
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            model = "devstral-small-2505"

        return LLMResponse(
            content=result_text,
            model=model,
            provider="vibe",
            usage=usage,
        )


# ---------------------------------------------------------------------------
# OpenAI Codex CLI Agent
# ---------------------------------------------------------------------------


class CodexAgent(Agent):
    """OpenAI Codex CLI coding agent.

    Uses `codex exec --quiet "..."` for non-interactive programmatic execution.
    """

    def __init__(
        self,
        workdir: str | None = None,
        full_auto: bool = True,
    ):
        super().__init__(
            name="codex",
            description="OpenAI Codex CLI — agent de code pour édition, review, exécution (o4-mini/o3)",
            system_prompt=(
                "You are the Codex CLI agent powered by OpenAI. "
                "Execute coding tasks: write, review, debug, run commands. "
                "Use full-auto mode for autonomous sandboxed execution."
            ),
            preferred_provider="openai",
            strategy=Strategy.SPECIFIC,
            temperature=0.2,
            max_tokens=8192,
        )
        self._workdir = workdir
        self._full_auto = full_auto

    @property
    def is_available(self) -> bool:
        return _cli_available("codex")

    async def run(
        self,
        prompt: str,
        *,
        router: Router | None = None,
        context: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Execute Codex CLI in non-interactive mode."""
        if not self.is_available:
            raise RuntimeError(
                "codex CLI not found. Install: npm install -g @openai/codex"
            )

        cmd = ["codex", "exec"]
        if self._full_auto:
            cmd.append("--full-auto")
        cmd.extend(["--skip-git-repo-check", prompt])

        stdout, stderr, code = await _run_cli(cmd, workdir=self._workdir)

        content = stdout.strip() or stderr.strip()

        return LLMResponse(
            content=content,
            model="o4-mini",
            provider="codex-cli",
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )


# ---------------------------------------------------------------------------
# Claude Code CLI Agent
# ---------------------------------------------------------------------------


class ClaudeCodeAgent(Agent):
    """Claude Code CLI coding agent.

    Uses `claude --print --output-format json "..."` for non-interactive
    programmatic execution.
    """

    def __init__(
        self,
        workdir: str | None = None,
        model: str = "sonnet",
        allowed_tools: list[str] | None = None,
    ):
        super().__init__(
            name="claude-code",
            description="Claude Code CLI — agent de code Anthropic pour architecture, refactoring, debugging (Sonnet/Opus)",
            system_prompt=(
                "You are the Claude Code CLI agent powered by Anthropic. "
                "Execute coding tasks: architecture, implementation, review, testing. "
                "Use available tools: Read, Edit, Write, Bash, Grep, Glob."
            ),
            preferred_provider="claude",
            strategy=Strategy.SPECIFIC,
            temperature=0.2,
            max_tokens=16384,
        )
        self._workdir = workdir
        self._model = model
        self._allowed_tools = allowed_tools

    @property
    def is_available(self) -> bool:
        return _cli_available("claude")

    async def run(
        self,
        prompt: str,
        *,
        router: Router | None = None,
        context: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Execute Claude Code in print mode."""
        if not self.is_available:
            raise RuntimeError(
                "claude CLI not found. Install: npm install -g @anthropic-ai/claude-code"
            )

        cmd = [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--model",
            self._model,
            "--verbose",
        ]
        if self._workdir:
            cmd.extend(["--add-dir", self._workdir])
        if self._allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self._allowed_tools)])

        cmd.extend(["--", prompt])

        stdout, stderr, code = await _run_cli(
            cmd, workdir=self._workdir, timeout=600  # Claude can be slow
        )

        # Parse JSON output
        content = stdout.strip()
        try:
            data = json.loads(content)
            result_text = data.get("result", content)
            if isinstance(result_text, dict):
                result_text = result_text.get("text", json.dumps(result_text))
            usage = {
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
            }
            model = data.get("model", f"claude-{self._model}")
        except (json.JSONDecodeError, KeyError):
            result_text = content or stderr
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            model = f"claude-{self._model}"

        return LLMResponse(
            content=result_text,
            model=model,
            provider="claude-code",
            usage=usage,
        )


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_cli_agents(registry) -> None:
    """Register available CLI agents in the agent registry."""
    agents = [
        (VibeAgent, "vibe"),
        (CodexAgent, "codex"),
        (ClaudeCodeAgent, "claude"),
    ]
    for agent_cls, binary in agents:
        if _cli_available(binary):
            try:
                agent = agent_cls()
                registry.register(agent, builtin=True)
                logger.info("CLI agent registered: %s", agent.name)
            except Exception as exc:
                logger.warning("Failed to register CLI agent %s: %s", binary, exc)
        else:
            logger.debug("CLI agent %s not available (binary not in PATH)", binary)
