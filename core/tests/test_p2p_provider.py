"""Tests for the P2P LLM provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from mascarade.router.providers.p2p import P2PProvider


# ── Fakes ────────────────────────────────────────────────────────────


@dataclass
class FakePeerCapabilities:
    peer_id: str
    capabilities: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    provider_models: dict[str, list[str]] = field(default_factory=dict)


class FakeCapabilityExchange:
    def __init__(self, peers: list[FakePeerCapabilities] | None = None) -> None:
        self._peers = {p.peer_id: p for p in (peers or [])}

    def all_capabilities(self) -> dict:
        return dict(self._peers)

    def peers_with_provider(self, provider: str) -> list:
        return [p for p in self._peers.values() if provider in p.providers]

    def peers_with_model(self, provider: str, model: str) -> list:
        return [
            p for p in self._peers.values()
            if model in p.provider_models.get(provider, [])
        ]


class FakeForwarder:
    def __init__(
        self,
        *,
        reachable: set[str] | None = None,
        response: dict | None = None,
    ) -> None:
        self._reachable = reachable or set()
        self._response = response or {
            "content": "hello from peer",
            "model": "claude-3-5-sonnet",
            "provider": "claude",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        self.calls: list[dict] = []

    def can_forward(self, peer_id: str) -> bool:
        return peer_id in self._reachable

    async def forward_request(self, peer_id: str, data: dict, timeout: float = 120.0) -> dict:
        self.calls.append({"peer_id": peer_id, "data": data, "timeout": timeout})
        return dict(self._response)


# ── Tests ────────────────────────────────────────────────────────────


def _make_provider(
    *,
    p2p_enabled: bool = True,
    p2p_provider_enabled: bool = True,
) -> P2PProvider:
    with patch("mascarade.router.providers.p2p.settings") as mock_settings:
        mock_settings.p2p_enabled = p2p_enabled
        mock_settings.p2p_provider_enabled = p2p_provider_enabled
        mock_settings.p2p_provider_timeout_seconds = 30.0
        mock_settings.cluster_shared_key = ""
        provider = P2PProvider()
    return provider


class TestIsConfigured:
    def test_configured_when_both_enabled(self):
        prov = _make_provider()
        with patch("mascarade.router.providers.p2p.settings") as s:
            s.p2p_enabled = True
            s.p2p_provider_enabled = True
            assert prov.is_configured is True

    def test_not_configured_when_p2p_disabled(self):
        prov = _make_provider()
        with patch("mascarade.router.providers.p2p.settings") as s:
            s.p2p_enabled = False
            s.p2p_provider_enabled = True
            assert prov.is_configured is False

    def test_not_configured_when_provider_disabled(self):
        prov = _make_provider()
        with patch("mascarade.router.providers.p2p.settings") as s:
            s.p2p_enabled = True
            s.p2p_provider_enabled = False
            assert prov.is_configured is False


class TestAvailableModels:
    def test_empty_without_capabilities(self):
        prov = _make_provider()
        assert prov.available_models() == []

    def test_aggregates_peer_models(self):
        prov = _make_provider()
        caps = FakeCapabilityExchange([
            FakePeerCapabilities(
                peer_id="peer-a",
                providers=["claude"],
                provider_models={"claude": ["claude-3-5-sonnet"]},
            ),
            FakePeerCapabilities(
                peer_id="peer-b",
                providers=["ollama"],
                provider_models={"ollama": ["qwen2.5:7b", "llama3:8b"]},
            ),
        ])
        prov.attach_p2p(FakeForwarder(), caps)
        models = prov.available_models()
        assert "claude:claude-3-5-sonnet" in models
        assert "ollama:qwen2.5:7b" in models
        assert "ollama:llama3:8b" in models


class TestResolvePeer:
    def _setup(self, reachable: set[str] | None = None):
        prov = _make_provider()
        peers = [
            FakePeerCapabilities(
                peer_id="peer-a",
                capabilities=["llm-inference"],
                providers=["claude"],
                provider_models={"claude": ["claude-3-5-sonnet"]},
            ),
            FakePeerCapabilities(
                peer_id="peer-b",
                capabilities=["llm-inference"],
                providers=["ollama"],
                provider_models={"ollama": ["qwen2.5:7b"]},
            ),
        ]
        caps = FakeCapabilityExchange(peers)
        forwarder = FakeForwarder(reachable=reachable or {"peer-a", "peer-b"})
        prov.attach_p2p(forwarder, caps)
        return prov

    def test_explicit_peer(self):
        prov = self._setup()
        peer_id, provider, model = prov._resolve_peer("peer-a/claude:claude-3-5-sonnet")
        assert peer_id == "peer-a"
        assert provider == "claude"
        assert model == "claude-3-5-sonnet"

    def test_provider_model(self):
        prov = self._setup()
        peer_id, provider, model = prov._resolve_peer("claude:claude-3-5-sonnet")
        assert peer_id == "peer-a"
        assert provider == "claude"
        assert model == "claude-3-5-sonnet"

    def test_any_peer(self):
        prov = self._setup()
        peer_id, provider, model = prov._resolve_peer(None)
        assert peer_id in ("peer-a", "peer-b")
        assert provider is None

    def test_no_reachable_peer_raises(self):
        prov = self._setup(reachable=set())
        with pytest.raises(ConnectionError, match="No reachable P2P peer"):
            prov._resolve_peer("claude:claude-3-5-sonnet")

    def test_not_connected_raises(self):
        prov = _make_provider()
        with pytest.raises(ConnectionError, match="not connected"):
            prov._resolve_peer(None)


class TestSend:
    @pytest.mark.asyncio
    async def test_send_forwards_to_peer(self):
        prov = _make_provider()
        forwarder = FakeForwarder(reachable={"peer-a"})
        caps = FakeCapabilityExchange([
            FakePeerCapabilities(
                peer_id="peer-a",
                capabilities=["llm-inference"],
                providers=["claude"],
                provider_models={"claude": ["sonnet"]},
            ),
        ])
        prov.attach_p2p(forwarder, caps)

        resp = await prov.send(
            [{"role": "user", "content": "hello"}],
            model="claude:sonnet",
        )
        assert resp.content == "hello from peer"
        assert "p2p/peer-a" in resp.provider
        assert len(forwarder.calls) == 1
        call = forwarder.calls[0]
        assert call["peer_id"] == "peer-a"
        assert call["data"]["provider"] == "claude"
        assert call["data"]["strategy"] == "specific"

    @pytest.mark.asyncio
    async def test_stream_yields_content(self):
        prov = _make_provider()
        forwarder = FakeForwarder(reachable={"peer-a"})
        caps = FakeCapabilityExchange([
            FakePeerCapabilities(
                peer_id="peer-a",
                capabilities=["llm-inference"],
                providers=["claude"],
                provider_models={"claude": ["sonnet"]},
            ),
        ])
        prov.attach_p2p(forwarder, caps)

        tokens = []
        async for token in prov.stream(
            [{"role": "user", "content": "hi"}],
            model="claude:sonnet",
        ):
            tokens.append(token)
        assert tokens == ["hello from peer"]
