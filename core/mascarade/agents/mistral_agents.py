"""Mistral AI Studio agents — bridge avec les agents distants Mistral.

Intègre les agents créés dans Mistral AI Studio (Devstral-Code, Forge,
Tower, Sentinelle) comme agents mascarade, en les appelant via l'API
Conversations beta de Mistral.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from mascarade.agents.base import Agent
from mascarade.config import is_secret_configured, secret_value, settings
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy

logger = logging.getLogger("mascarade.agents.mistral_agents")


@dataclass
class MistralRemoteAgent(Agent):
    """Agent mascarade qui délègue à un agent Mistral AI Studio.

    Appelle l'API beta conversations de Mistral pour exécuter l'agent distant,
    puis retourne le résultat comme un LLMResponse standard.
    """

    agent_id: str = ""
    conversation_id: str | None = None  # for stateful conversations

    async def run(
        self,
        prompt: str,
        *,
        router: Router | None = None,
        context: list[dict] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Exécuter l'agent Mistral distant via l'API Conversations."""
        import httpx

        api_key = secret_value(settings.mistral_api_key).strip()
        if not is_secret_configured(api_key):
            raise RuntimeError("MISTRAL_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            if self.conversation_id:
                # Continue existing conversation
                url = f"https://api.mistral.ai/v1/conversations/{self.conversation_id}"
                payload: dict[str, Any] = {
                    "inputs": prompt,
                    "stream": False,
                }
            else:
                # Start new conversation
                url = "https://api.mistral.ai/v1/conversations"
                payload = {
                    "agent_id": self.agent_id,
                    "inputs": prompt,
                    "stream": False,
                }

            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Store conversation_id for follow-ups
        self.conversation_id = data.get("conversation_id")

        # Extract response
        outputs = data.get("outputs", [])
        content = ""
        if outputs:
            content = outputs[-1].get("content", "")

        usage_data = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=f"mistral-agent:{self.name}",
            provider="mistral-agents",
            usage={
                "input_tokens": usage_data.get("prompt_tokens", 0),
                "output_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            },
        )

    def reset_conversation(self) -> None:
        """Reset conversation state for a fresh start."""
        self.conversation_id = None

    async def register_mcp_tools(self, mcp_server_url: str) -> None:
        """Register mascarade's MCP server as a tool source for this Mistral agent.

        This allows the Mistral agent to call back into mascarade tools
        via the MCP (Model Context Protocol) integration.

        The MCP server URL is sent to the Mistral agent configuration so that
        tool calls from the agent are routed back to mascarade's MCP endpoint.

        Parameters
        ----------
        mcp_server_url:
            Full URL of the mascarade MCP server
            (e.g. ``"http://localhost:8100/v1/mcp"``).
        """
        import httpx

        api_key = secret_value(settings.mistral_api_key).strip()
        if not is_secret_configured(api_key):
            raise RuntimeError("MISTRAL_API_KEY not configured")

        if not self.agent_id:
            raise ValueError("agent_id must be set before registering MCP tools")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "tools": [
                {
                    "type": "mcp",
                    "mcp": {
                        "url": mcp_server_url,
                        "type": "sse",
                    },
                }
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"https://api.mistral.ai/v1/agents/{self.agent_id}",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

        logger.info(
            "MCP tools registered for agent %s (%s) -> %s",
            self.name,
            self.agent_id,
            mcp_server_url,
        )


async def discover_mistral_agents() -> list[dict[str, str]]:
    """Discover agents from Mistral AI Studio API.

    Returns list of {"id": "ag:...", "name": "...", "description": "..."}.
    """
    import httpx

    api_key = secret_value(settings.mistral_api_key).strip()
    if not is_secret_configured(api_key):
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.mistral.ai/v1/agents",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"page": 0, "page_size": 50},
            )
            resp.raise_for_status()
            data = resp.json()

        agents = []
        items = data if isinstance(data, list) else data.get("data", data.get("agents", []))
        for agent in items:
            agents.append({
                "id": agent.get("id", ""),
                "name": agent.get("name", ""),
                "description": agent.get("description", ""),
                "model": agent.get("model", ""),
            })
        return agents

    except Exception as exc:
        logger.warning("Failed to discover Mistral agents: %s", exc)
        return []


def register_mistral_agents(registry, agents_config: list[dict] | None = None) -> None:
    """Register Mistral AI Studio agents in the mascarade registry.

    If agents_config is provided, uses that. Otherwise uses hardcoded
    known agents from L'Electron Rare workspace.
    """
    if agents_config is None:
        agents_config = _DEFAULT_AGENTS

    api_key = getattr(settings, "mistral_api_key", "")
    if not is_secret_configured(api_key):
        logger.debug("Mistral API key not configured, skipping agent registration")
        return

    for cfg in agents_config:
        agent = MistralRemoteAgent(
            name=cfg["name"],
            description=cfg["description"],
            system_prompt=cfg.get("system_prompt", ""),
            agent_id=cfg["agent_id"],
            preferred_provider="mistral",
            strategy=Strategy.SPECIFIC,
            temperature=cfg.get("temperature", 0.3),
            max_tokens=cfg.get("max_tokens", 8192),
        )
        registry.register(agent, builtin=True)
        logger.info("Mistral remote agent registered: %s (%s)", cfg["name"], cfg["agent_id"])


# --- Default Mistral agents from L'Electron Rare AI Studio workspace ---

_DEFAULT_AGENTS: list[dict[str, Any]] = [
    {
        "name": "devstral-code",
        "agent_id": "",  # À remplir avec l'ID réel depuis AI Studio
        "description": (
            "Agent de développement code pour le workflow agentique saillant.cc. "
            "Génération, refactoring, review, debugging via Devstral."
        ),
        "system_prompt": (
            "Tu es Devstral-Code, un agent de développement expert. "
            "Tu génères, refactores, reviews et debugs du code pour l'écosystème saillant.cc / mascarade. "
            "Tu connais Python, TypeScript, React, FastAPI, Docker, et les patterns agentiques."
        ),
        "temperature": 0.2,
        "max_tokens": 16384,
    },
    {
        "name": "forge",
        "agent_id": "",  # À remplir
        "description": (
            "Agent de pilotage fine-tuning de Mascarade. "
            "Pipeline DPO/SimPO/KTO/RLVR, gestion des runs, évaluation."
        ),
        "system_prompt": (
            "Tu es Forge, l'agent de pilotage du fine-tuning mascarade. "
            "Tu gères les pipelines d'entraînement (DPO, SimPO, KTO, RLVR), "
            "les datasets, l'évaluation des modèles et le déploiement. "
            "Tu connais Unsloth, TRL, LoRA, et les 11 domaines spécialisés."
        ),
        "temperature": 0.3,
        "max_tokens": 8192,
    },
    {
        "name": "tower-commercial",
        "agent_id": "",  # À remplir
        "description": (
            "Agent commercial de l'écosystème saillant.cc. "
            "Scoring leads, nurturing, qualification, CRM."
        ),
        "system_prompt": (
            "Tu es Tower, l'agent commercial de saillant.cc. "
            "Tu scores les leads, qualifies les prospects, nurtures les contacts, "
            "et gères les interactions CRM pour L'Electron Rare."
        ),
        "temperature": 0.5,
        "max_tokens": 4096,
    },
    {
        "name": "sentinelle",
        "agent_id": "",  # À remplir
        "description": (
            "Agent ops/monitoring de l'écosystème saillant.cc. "
            "Diagnostique, surveille, alerte, analyse les incidents."
        ),
        "system_prompt": (
            "Tu es Sentinelle, l'agent ops de saillant.cc. "
            "Tu diagnostiques les problèmes, surveilles les services, "
            "analyses les métriques et traces, et proposes des remédiations."
        ),
        "temperature": 0.2,
        "max_tokens": 8192,
    },
]
