"""Adaptateur Mistral Agents — Beta Conversations API.

Provider dédié aux agents Mistral AI Studio déclarés via la configuration
Mascarade. Utilise en priorité l'endpoint Beta ``/v1/conversations`` avec
fallback vers ``/v1/agents/{id}/completions``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from mascarade.config import is_secret_configured, secret_value, settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

logger = logging.getLogger("mascarade.providers.mistral_agents")

_retry = make_retry(httpx.TimeoutException, httpx.TransportError)

_AGENT_DEFS: tuple[dict[str, Any], ...] = (
    {
        "name": "sentinelle",
        "aliases": ("sentinelle",),
        "setting_attr": "mistral_agent_sentinelle_id",
        "model": "mistral-medium-latest",
        "temperature": 0.1,
        "role": "Ops/Monitoring",
    },
    {
        "name": "tower",
        "aliases": ("tower", "tower-commercial"),
        "setting_attr": "mistral_agent_tower_id",
        "model": "magistral-medium-latest",
        "temperature": 0.4,
        "role": "Commercial/CRM",
    },
    {
        "name": "forge",
        "aliases": ("forge",),
        "setting_attr": "mistral_agent_forge_id",
        "model": "codestral-latest",
        "temperature": 0.21,
        "role": "Fine-tune Pipeline",
    },
    {
        "name": "devstral-code",
        "aliases": ("devstral", "devstral-code"),
        "setting_attr": "mistral_agent_devstral_id",
        "model": "devstral-latest",
        "temperature": 0.17,
        "role": "Code/Dev Workflow",
    },
)


def _base_url() -> str:
    return settings.mistral_api_base.rstrip("/") or "https://api.mistral.ai/v1"


def _agent_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for spec in _AGENT_DEFS:
        agent_id = str(getattr(settings, spec["setting_attr"], "") or "").strip()
        agent = {
            "name": spec["name"],
            "id": agent_id,
            "model": spec["model"],
            "temperature": spec["temperature"],
            "role": spec["role"],
            "aliases": tuple(spec["aliases"]),
            "configured": bool(agent_id),
        }
        catalog[spec["name"]] = agent
    return catalog


def _configured_agents() -> dict[str, dict[str, Any]]:
    return {
        name: agent
        for name, agent in _agent_catalog().items()
        if agent["configured"]
    }


def _extract_content(data: dict[str, Any]) -> tuple[str, dict[str, int]]:
    if "outputs" in data:
        outputs = data.get("outputs", [])
        assistant_outputs = [item for item in outputs if item.get("role") == "assistant"]
        latest = assistant_outputs[-1] if assistant_outputs else (outputs[-1] if outputs else {})
        content = latest.get("content", "")
        if isinstance(content, list):
            text_chunks = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            content = "\n".join(chunk for chunk in text_chunks if chunk)
        usage_raw = data.get("usage", {})
        return str(content or ""), {
            "input_tokens": usage_raw.get("prompt_tokens", 0),
            "output_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }

    choices = data.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        usage_raw = data.get("usage", {})
        return str(message.get("content", "")), {
            "input_tokens": usage_raw.get("prompt_tokens", 0),
            "output_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }

    error = data.get("message", data.get("error", "no response"))
    raise RuntimeError(f"Mistral agent error: {error}")


@dataclass
class AgentResponse:
    """Réponse structurée d'un appel agent."""

    content: str
    agent_name: str
    agent_id: str
    conversation_id: str | None = None
    api_mode: str = "beta"
    usage: dict[str, int] = field(default_factory=dict)


class MistralAgentsProvider(LLMProvider):
    """Provider Mascarade pour les agents Mistral via Conversations API."""

    name = "mistral-agents"
    default_model = "agent:sentinelle"
    cost_per_million = (2.0, 6.0)
    speed_rank = 2
    quality_rank = 2

    def __init__(self) -> None:
        self._api_key = secret_value(settings.mistral_api_key).strip()
        self._base_url = _base_url()
        self._timeout = max(settings.mistral_timeout_ms / 1000, 1)
        self._api_mode = str(getattr(settings, "mistral_agents_api_mode", "beta") or "beta").strip().lower()
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._timeout),
            )
        return self._http

    @property
    def is_configured(self) -> bool:
        return is_secret_configured(self._api_key) and bool(_configured_agents())

    def _resolve_agent(self, model: str | None) -> dict[str, Any]:
        configured = _configured_agents()
        if not configured:
            raise RuntimeError("No Mistral agents configured")

        if model is None:
            return next(iter(configured.values()))

        normalized = model.lower().strip().removeprefix("agent:")
        for agent in configured.values():
            if normalized == agent["name"] or normalized in agent["aliases"]:
                return agent
            if agent["id"] and normalized == str(agent["id"]).lower():
                return agent

        if model.startswith("ag_"):
            return {
                "name": model,
                "id": model,
                "model": self.default_model,
                "temperature": 0.3,
                "role": "ad-hoc",
                "aliases": (),
                "configured": True,
            }

        raise RuntimeError(f"Unknown configured Mistral agent: {model}")

    async def _call_beta(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
        *,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        client = await self._get_client()
        payload: dict[str, Any]
        if conversation_id:
            payload = {"inputs": messages, "stream": False}
            response = await client.post(f"/conversations/{conversation_id}", json=payload)
        else:
            payload = {"agent_id": agent_id, "inputs": messages, "stream": False}
            response = await client.post("/conversations", json=payload)
        response.raise_for_status()
        return response.json()

    async def _call_deprecated(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.post(
            f"/agents/{agent_id}/completions",
            json={"messages": messages},
        )
        response.raise_for_status()
        return response.json()

    @_retry
    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        del response_format, temperature, max_tokens
        agent = self._resolve_agent(model)

        chat_messages: list[dict[str, Any]] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        data: dict[str, Any] | None = None
        if self._api_mode == "beta":
            try:
                data = await self._call_beta(agent["id"], chat_messages)
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning(
                    "Beta API failed for Mistral agent %s, fallback deprecated: %s",
                    agent["name"],
                    exc,
                )

        if data is None:
            data = await self._call_deprecated(agent["id"], chat_messages)

        content, usage = _extract_content(data)
        return LLMResponse(
            content=content,
            model=f"agent:{agent['name']}",
            provider=self.name,
            usage=usage,
        )

    async def send_to_agent(
        self,
        agent_name: str,
        message: str,
        *,
        system: str | None = None,
        conversation_id: str | None = None,
    ) -> AgentResponse:
        agent = self._resolve_agent(agent_name)
        chat_messages: list[dict[str, Any]] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.append({"role": "user", "content": message})

        data: dict[str, Any] | None = None
        if self._api_mode == "beta":
            try:
                data = await self._call_beta(
                    agent["id"],
                    chat_messages,
                    conversation_id=conversation_id,
                )
            except (httpx.HTTPStatusError, httpx.TransportError):
                data = await self._call_deprecated(agent["id"], chat_messages)

        if data is None:
            data = await self._call_deprecated(agent["id"], chat_messages)

        content, usage = _extract_content(data)
        return AgentResponse(
            content=content,
            agent_name=agent["name"],
            agent_id=agent["id"],
            conversation_id=data.get("conversation_id"),
            api_mode="beta" if "outputs" in data else "deprecated",
            usage=usage,
        )

    async def handoff(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
        *,
        transform_prompt: str = "Basé sur cette analyse: {context} — Propose une solution.",
    ) -> tuple[AgentResponse, AgentResponse]:
        first = await self.send_to_agent(from_agent, message)
        second = await self.send_to_agent(
            to_agent,
            transform_prompt.format(context=first.content),
        )
        logger.info("Mistral handoff %s -> %s completed", from_agent, to_agent)
        return first, second

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        response = await self.send(
            messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield response.content

    def available_models(self) -> list[str]:
        return [f"agent:{name}" for name in _configured_agents()]

    def list_agents(self) -> dict[str, dict[str, Any]]:
        return _agent_catalog()

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
