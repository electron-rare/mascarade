"""P2P Proxy Provider — routes LLM requests to remote Mascarade peers.

This provider behaves like any other LLMProvider but forwards requests
to a remote peer's HTTP API.  It integrates seamlessly with the router's
strategy, load balancer, and circuit breaker logic.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from mascarade.router.providers.base import LLMProvider, LLMResponse, LLMStreamChunk

logger = logging.getLogger("mascarade.providers.p2p_proxy")


@dataclass
class P2PProxyProvider(LLMProvider):
    """LLM provider that forwards requests to a remote Mascarade peer."""

    name: str = "p2p"
    peer_id: str = ""
    peer_label: str = ""
    peer_url: str = ""  # e.g. http://192.168.0.119:8100
    peer_providers: list[str] = field(default_factory=list)
    peer_models: dict[str, list[str]] = field(default_factory=dict)
    default_model: str = ""
    cost_per_million: tuple[float, float] = (0.0, 0.0)  # unknown
    speed_rank: int = 50  # medium — network latency
    quality_rank: int = 80  # depends on peer's providers
    timeout: float = 120.0

    @property
    def is_configured(self) -> bool:
        return bool(self.peer_url)

    def available_models(self) -> list[str]:
        """All models available on this peer, prefixed with provider."""
        models = []
        for provider, model_list in self.peer_models.items():
            for m in model_list:
                models.append(f"{provider}:{m}")
        return models

    def has_model(self, provider: str, model: str) -> bool:
        """Check if this peer has a specific provider:model."""
        return model in self.peer_models.get(provider, [])

    def has_provider(self, provider: str) -> bool:
        return provider in self.peer_providers

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Forward a chat completion to the remote peer."""
        url = f"{self.peer_url}/v1/chat/completions"

        # Parse provider:model if present
        provider_hint = None
        model_name = model
        if model and ":" in model:
            parts = model.split(":", 1)
            if not parts[1].replace(".", "").replace("-", "").isdigit():
                provider_hint = parts[0]
                model_name = parts[1]

        body: dict[str, Any] = {
            "model": model_name or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            body["messages"] = [{"role": "system", "content": system}] + body["messages"]
        if provider_hint:
            body["provider"] = provider_hint

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("P2P peer %s returned %s: %s", self.peer_id, e.response.status_code, e)
            raise ConnectionError(f"P2P peer {self.peer_id} error: {e}") from e
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            logger.warning("P2P peer %s unreachable: %s", self.peer_id, e)
            raise ConnectionError(f"P2P peer {self.peer_id} unreachable: {e}") from e

        # Parse OpenAI-format response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return LLMResponse(
            content=message.get("content", ""),
            model=data.get("model", model or "unknown"),
            provider=f"p2p/{self.peer_id}",
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a chat completion from the remote peer."""
        url = f"{self.peer_url}/v1/chat/completions"

        body: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system:
            body["messages"] = [{"role": "system", "content": system}] + body["messages"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


def build_p2p_providers(
    peer_capabilities: dict[str, Any],
) -> list[P2PProxyProvider]:
    """Build P2P proxy providers from a capability exchange snapshot.

    Args:
        peer_capabilities: Dict of peer_id -> PeerCapabilities objects.

    Returns:
        List of P2PProxyProvider instances, one per reachable peer.
    """
    providers = []
    for peer_id, caps in peer_capabilities.items():
        if not getattr(caps, "http_base_url", None):
            continue
        providers.append(
            P2PProxyProvider(
                name=f"p2p/{peer_id}",
                peer_id=peer_id,
                peer_label=getattr(caps, "label", ""),
                peer_url=caps.http_base_url,
                peer_providers=getattr(caps, "providers", []),
                peer_models=getattr(caps, "provider_models", {}),
                default_model="",
                speed_rank=60,  # network latency penalty
                quality_rank=75,
            )
        )
    return providers
