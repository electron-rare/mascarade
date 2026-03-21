"""CLI coding agents router — Vibe, Codex, Claude Code endpoints."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

logger = logging.getLogger("mascarade.routers.cli_agents")

router = APIRouter(
    prefix="/api/cli-agents",
    dependencies=[Depends(require_auth)],
    tags=["cli-agents"],
)


class CLIAgentRequest(BaseModel):
    """Request to run a CLI coding agent."""

    prompt: str = Field(min_length=1, max_length=100_000)
    workdir: str | None = Field(default=None, max_length=500)
    agent: Literal["vibe", "codex", "claude-code"] = "claude-code"

    # Vibe-specific
    max_turns: int = Field(default=20, ge=1, le=100)
    max_price: float = Field(default=2.0, ge=0.0, le=50.0)

    # Claude-specific
    model: str = Field(default="sonnet", max_length=50)
    allowed_tools: list[str] | None = None

    # Codex-specific
    full_auto: bool = True


@router.get("/status")
async def cli_agents_status(request: Request):
    """Check availability of CLI coding agents."""
    from mascarade.agents.cli_agents import _cli_available

    return {
        "agents": {
            "vibe": {
                "available": _cli_available("vibe"),
                "binary": "vibe",
                "provider": "Mistral (Devstral)",
                "modes": ["chat", "fim"],
            },
            "codex": {
                "available": _cli_available("codex"),
                "binary": "codex",
                "provider": "OpenAI (o4-mini)",
                "modes": ["exec", "review"],
            },
            "claude-code": {
                "available": _cli_available("claude"),
                "binary": "claude",
                "provider": "Anthropic (Sonnet/Opus)",
                "modes": ["print", "interactive"],
            },
        }
    }


@router.post("/run")
async def run_cli_agent(req: CLIAgentRequest, request: Request):
    """Run a CLI coding agent with a prompt."""
    from mascarade.agents.cli_agents import (
        ClaudeCodeAgent,
        CodexAgent,
        VibeAgent,
        _cli_available,
    )

    agent_map = {
        "vibe": lambda: VibeAgent(
            max_turns=req.max_turns,
            max_price=req.max_price,
            workdir=req.workdir,
        ),
        "codex": lambda: CodexAgent(
            workdir=req.workdir,
            full_auto=req.full_auto,
        ),
        "claude-code": lambda: ClaudeCodeAgent(
            workdir=req.workdir,
            model=req.model,
            allowed_tools=req.allowed_tools,
        ),
    }

    binary_map = {"vibe": "vibe", "codex": "codex", "claude-code": "claude"}

    binary = binary_map[req.agent]
    if not _cli_available(binary):
        raise HTTPException(
            status_code=503,
            detail=f"CLI agent '{req.agent}' not available ({binary} not in PATH)",
        )

    agent = agent_map[req.agent]()
    try:
        response = await agent.run(req.prompt)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("CLI agent %s failed: %s", req.agent, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "agent": req.agent,
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }
