"""P2P Provider — forward LLM requests to peers with llm-inference capability."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from mascarade.config import settings
from mascarade.router.model_sizes import can_fit_in_vram, get_model_size_gb
from mascarade.router.providers.base import LLMProvider, LLMResponse

if TYPE_CHECKING:
    from mascarade.p2p.capabilities import P2PCapabilityExchange
    from mascarade.p2p.stream_forward import P2PStreamForwarder

logger = logging.getLogger("mascarade.providers.p2p")


class P2PProvider(LLMProvider):
    """Route LLM requests to remote peers via the P2P mesh network."""

    name = "p2p"
    default_model = "best"
    cost_per_million = (0.0, 0.0)
    speed_rank = 5
    quality_rank = 3

    def __init__(self) -> None:
        self._forwarder: P2PStreamForwarder | None = None
        self._capabilities: P2PCapabilityExchange | None = None
        self._timeout = settings.p2p_provider_timeout_seconds

    def attach_p2p(
        self,
        forwarder: P2PStreamForwarder,
        capabilities: P2PCapabilityExchange,
    ) -> None:
        """Wire the provider to a running P2P node.  Called by ClusterManager."""
        self._forwarder = forwarder
        self._capabilities = capabilities
        logger.info("P2PProvider attached to P2P node")

    @property
    def is_configured(self) -> bool:
        return settings.p2p_enabled and settings.p2p_provider_enabled

    # ── send ─────────────────────────────────────────────────────────

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **_extra,
    ) -> LLMResponse:
        peer_id, target_provider, target_model = self._resolve_peer(model)

        request_data = {
            "messages": messages,
            "system": system,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if target_provider:
            request_data["provider"] = target_provider
            request_data["strategy"] = "specific"
        else:
            request_data["strategy"] = "best"
        if target_model:
            request_data["model"] = target_model

        # Inject cluster token for auth on the receiving end
        shared_key = settings.cluster_shared_key.strip()
        if shared_key:
            request_data["__cluster_token"] = shared_key

        if self._forwarder is None:
            raise RuntimeError("P2P forwarder not initialized")
        result = await self._forwarder.forward_request(
            peer_id,
            request_data,
            timeout=self._timeout,
        )

        return LLMResponse(
            content=result.get("content", ""),
            model=result.get("model", model or "unknown"),
            provider=f"p2p/{peer_id}/{result.get('provider', 'unknown')}",
            usage=result.get("usage", {}),
        )

    # ── stream ───────────────────────────────────────────────────────

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **_extra,
    ) -> AsyncIterator[str]:
        # P2P stream forwarder is request/response — full send then yield.
        response = await self.send(
            messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield response.content

    # ── models ───────────────────────────────────────────────────────

    def available_models(self) -> list[str]:
        if not self._capabilities:
            return []
        models: set[str] = set()
        for caps in self._capabilities.all_capabilities().values():
            for provider, provider_models in caps.provider_models.items():
                for m in provider_models:
                    models.add(f"{provider}:{m}")
        return sorted(models)

    # ── internals ────────────────────────────────────────────────────

    def _resolve_peer(
        self,
        model: str | None,
    ) -> tuple[str, str | None, str | None]:
        """Pick the best reachable peer for the requested model.

        Model formats accepted:
        - ``"peer_id/provider:model"`` — explicit peer + provider + model
        - ``"provider:model"`` — find any peer with that provider/model
        - ``None`` — find any peer with ``llm-inference`` capability
        """
        if not self._capabilities or not self._forwarder:
            raise ConnectionError("P2P provider not connected — no P2P node running")

        target_provider: str | None = None
        target_model: str | None = model

        # Explicit peer_id/provider:model
        if model and "/" in model:
            parts = model.split("/", 1)
            peer_id = parts[0]
            if ":" in parts[1]:
                target_provider, target_model = parts[1].split(":", 1)
            else:
                target_model = parts[1]
            if not self._forwarder.can_forward(peer_id):
                raise ConnectionError(f"P2P peer {peer_id} is not reachable")
            return peer_id, target_provider, target_model

        # provider:model
        if model and ":" in model:
            target_provider, target_model = model.split(":", 1)

        # Find peers
        if target_provider and target_model:
            peers = self._capabilities.peers_with_model(target_provider, target_model)
        elif target_provider:
            peers = self._capabilities.peers_with_provider(target_provider)
        else:
            all_caps = self._capabilities.all_capabilities()
            peers = [c for c in all_caps.values() if "llm-inference" in c.capabilities]

        # Filter to reachable peers
        reachable = [p for p in peers if self._forwarder.can_forward(p.peer_id)]
        if not reachable:
            raise ConnectionError(
                f"No reachable P2P peer for model={model} "
                f"(found {len(peers)} peer(s), none reachable)"
            )

        # Hardware-aware selection: prefer peers with enough VRAM for the model
        model_gb = get_model_size_gb(target_model)
        if model_gb > 0.0:
            vram_capable = [
                p for p in reachable if can_fit_in_vram(target_model, p.gpu_vram_gb)
            ]
            if vram_capable:
                if len(vram_capable) < len(reachable):
                    logger.info(
                        "P2P VRAM filter: model=%s (%.1fGB) → %d/%d peers qualify",
                        target_model,
                        model_gb,
                        len(vram_capable),
                        len(reachable),
                    )
                reachable = vram_capable
            else:
                logger.warning(
                    "P2P: no peer has enough VRAM for %s (%.1fGB) — using all reachable",
                    target_model,
                    model_gb,
                )

        # Sort by VRAM descending so the most capable peer is preferred
        reachable.sort(key=lambda p: -p.gpu_vram_gb)
        chosen = reachable[0]
        logger.debug(
            "P2P resolved model=%s → peer=%s provider=%s (VRAM=%.1fGB)",
            model,
            chosen.peer_id,
            target_provider,
            chosen.gpu_vram_gb,
        )
        return chosen.peer_id, target_provider, target_model
