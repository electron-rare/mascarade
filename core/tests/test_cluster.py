"""Tests du mode cluster multi-noeud."""

from contextlib import asynccontextmanager

import httpx
import pytest
from pydantic import SecretStr

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.cluster import (
    ClusterManager,
    ClusterPeer,
    _mdns_peer_matches_local_fingerprint,
    parse_cluster_peers,
)
from mascarade.config import settings
from mascarade.server import app


@pytest.fixture(autouse=True)
def _restore_cluster_settings():
    snapshot = {
        "cluster_enabled": settings.cluster_enabled,
        "cluster_shared_key": settings.cluster_shared_key,
        "node_id": settings.node_id,
        "node_role": settings.node_role,
        "node_label": settings.node_label,
        "mesh_bind_host": settings.mesh_bind_host,
        "mesh_scheme": settings.mesh_scheme,
        "cluster_request_timeout_ms": settings.cluster_request_timeout_ms,
        "cluster_forward_enabled": settings.cluster_forward_enabled,
        "cluster_peers": settings.cluster_peers,
        "cluster_mdns_enabled": settings.cluster_mdns_enabled,
        "cluster_mdns_service": settings.cluster_mdns_service,
        "cluster_mdns_discovery_ttl_seconds": settings.cluster_mdns_discovery_ttl_seconds,
        "cluster_mdns_advertise": settings.cluster_mdns_advertise,
        "cluster_require_tls": settings.cluster_require_tls,
        "cluster_allow_insecure_loopback": settings.cluster_allow_insecure_loopback,
        "mascarade_api_key": settings.mascarade_api_key,
    }
    for key in get_active_api_keys():
        remove_api_key(key)
    settings.cluster_require_tls = False
    settings.cluster_allow_insecure_loopback = True
    yield
    for key, value in snapshot.items():
        setattr(settings, key, value)
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-key-001"}


class _RouterLike:
    available_providers = ["ollama", "mistral"]

    @staticmethod
    def provider_model_map():
        return {
            "ollama": ["llama3.2:3b", "qwen2.5:3b"],
            "mistral": ["mistral-large-latest"],
        }


def test_parse_cluster_peers_accepts_valid_entries_and_ignores_self():
    peers = parse_cluster_peers(
        "node-gpu|gpu|http://100.64.0.20:8100;node-1|general|http://100.64.0.10:8100;bad-entry",
        node_id="node-1",
    )

    assert len(peers) == 1
    assert peers[0].peer_id == "node-gpu"
    assert peers[0].role == "gpu"
    assert peers[0].base_url == "http://100.64.0.20:8100"


def test_parse_cluster_peers_rejects_duplicates():
    with pytest.raises(ValueError, match="Duplicate cluster peer id"):
        parse_cluster_peers(
            "node-gpu|gpu|http://100.64.0.20:8100;node-gpu|edge|http://100.64.0.21:8100",
            node_id="node-1",
        )


@pytest.mark.asyncio
async def test_cluster_identity_reports_disabled_cluster():
    add_api_key("test-key-001")
    settings.cluster_enabled = False
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"

    async with _client() as client:
        response = await client.get("/v1/cluster/identity", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["cluster_enabled"] is False
    assert response.json()["node_id"] == "node-1"


@pytest.mark.asyncio
async def test_cluster_node_identity_requires_cluster_auth():
    settings.cluster_enabled = True
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.mesh_bind_host = "100.64.0.10"

    async with _client() as client:
        missing = await client.get("/v1/cluster/node/identity")
        invalid = await client.get(
            "/v1/cluster/node/identity",
            headers={"Authorization": "Bearer wrong-cluster-key"},
        )
        valid = await client.get(
            "/v1/cluster/node/identity",
            headers={"Authorization": "Bearer cluster-key-123456"},
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["base_url"] == "http://100.64.0.10:8100"
    assert "provider_models" in valid.json()


@pytest.mark.asyncio
async def test_cluster_peers_uses_manager_probe(monkeypatch):
    add_api_key("test-key-001")
    settings.cluster_enabled = True
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.mesh_bind_host = "100.64.0.10"
    settings.cluster_peers = "node-gpu|gpu|http://100.64.0.20:8100"

    async def fake_probe():
        return [
            type(
                "PeerStatusLike",
                (),
                {
                    "to_dict": lambda self: {
                        "peer_id": "node-gpu",
                        "role": "gpu",
                        "base_url": "http://100.64.0.20:8100",
                        "ok": True,
                        "status": 200,
                        "latency_ms": 18,
                        "error": None,
                        "remote_node_id": "node-gpu",
                        "remote_label": "GPU Node",
                        "providers": ["ollama"],
                        "agents": 16,
                        "last_seen": "2026-03-07T12:00:00Z",
                    }
                },
            )()
        ]

    async with _client() as client:
        monkeypatch.setattr(app.state.cluster, "probe_peers", fake_probe)
        response = await client.get("/v1/cluster/peers", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["peers"][0]["peer_id"] == "node-gpu"


@pytest.mark.asyncio
async def test_cluster_manager_forward_send_returns_remote_payload(monkeypatch):
    settings.cluster_enabled = True
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.cluster_request_timeout_ms = 5000
    settings.cluster_peers = "node-gpu|gpu|http://100.64.0.20:8100"

    manager = ClusterManager(router=_RouterLike(), agents_count_provider=lambda: 1)

    async def fake_request_json(peer, method, path, *, json=None):
        assert peer.peer_id == "node-gpu"
        assert method == "POST"
        assert path == "/v1/cluster/node/send"
        assert json == {
            "messages": [{"role": "user", "content": "hello"}],
            "strategy": "routellm",
            "routing_policy": "strong",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "system": None,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        return {
            "node_id": "node-gpu",
            "content": "remote hello",
            "model": "llama3.2:3b",
            "provider": "ollama",
            "usage": {"input_tokens": 2, "output_tokens": 3},
        }

    monkeypatch.setattr(manager, "_request_json", fake_request_json)

    result = await manager.forward_send(
        peer_id="node-gpu",
        payload={
            "messages": [{"role": "user", "content": "hello"}],
            "strategy": "routellm",
            "routing_policy": "strong",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "system": None,
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    )

    assert result["remote"] is True
    assert result["peer_id"] == "node-gpu"
    assert result["node_id"] == "node-gpu"
    assert result["content"] == "remote hello"


@pytest.mark.asyncio
async def test_cluster_manager_forward_send_no_double_execution(monkeypatch):
    """Bug fix: forward_send must NOT fire two HTTP requests.
    It should try P2P first, then fall back to HTTP only if P2P fails."""
    settings.cluster_enabled = True
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.cluster_request_timeout_ms = 5000
    settings.cluster_peers = "node-gpu|gpu|http://100.64.0.20:8100"

    manager = ClusterManager(router=_RouterLike(), agents_count_provider=lambda: 1)

    http_call_count = 0

    async def counting_request_json(peer, method, path, *, json=None):
        nonlocal http_call_count
        http_call_count += 1
        return {
            "node_id": "node-gpu",
            "content": "remote hello",
            "model": "llama3.2:3b",
            "provider": "ollama",
            "usage": {"input_tokens": 2, "output_tokens": 3},
        }

    monkeypatch.setattr(manager, "_request_json", counting_request_json)

    await manager.forward_send(
        peer_id="node-gpu",
        payload={
            "messages": [{"role": "user", "content": "hello"}],
            "strategy": "routellm",
            "routing_policy": "strong",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "system": None,
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    )

    # Without fix: http_call_count == 2 (pre-P2P + fallback)
    # With fix: http_call_count == 1 (only fallback after P2P returns None)
    assert http_call_count == 1, f"Expected exactly 1 HTTP call (fallback), got {http_call_count}"


@pytest.mark.asyncio
async def test_cluster_manager_forward_send_uses_libp2p_when_available(monkeypatch):
    settings.cluster_enabled = True
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.cluster_request_timeout_ms = 5000
    settings.cluster_peers = ""

    manager = ClusterManager(router=_RouterLike(), agents_count_provider=lambda: 1)

    class _Libp2PPeer:
        peer_id = "node-gpu"
        role = "gpu"
        base_url = "http://100.64.0.20:8100"
        libp2p_peer_id = "12D3KooWRemotePeer"

    class _FakeLibp2PNode:
        def __init__(self):
            self.forward_calls = []

        def discovered_peers(self):
            return [_Libp2PPeer()]

        async def forward_send(self, libp2p_peer_id, payload):
            self.forward_calls.append((libp2p_peer_id, payload))
            return {
                "node_id": "node-gpu",
                "content": "remote hello over p2p",
                "model": "llama3.2:3b",
                "provider": "ollama",
                "usage": {"input_tokens": 2, "output_tokens": 3},
            }

    fake_node = _FakeLibp2PNode()
    manager.set_p2p_node(fake_node)

    async def fail_http(*args, **kwargs):
        raise AssertionError("HTTP fallback should not be used when libp2p forwarding succeeds")

    monkeypatch.setattr(manager, "_request_json", fail_http)

    result = await manager.forward_send(
        peer_id="node-gpu",
        payload={
            "messages": [{"role": "user", "content": "hello"}],
            "strategy": "routellm",
            "routing_policy": "strong",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "system": None,
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    )

    assert fake_node.forward_calls == [
        (
            "12D3KooWRemotePeer",
            {
                "messages": [{"role": "user", "content": "hello"}],
                "strategy": "routellm",
                "routing_policy": "strong",
                "provider": "ollama",
                "model": "llama3.2:3b",
                "system": None,
                "temperature": 0.7,
                "max_tokens": 2048,
                "__cluster_token": "cluster-key-123456",
            },
        )
    ]
    assert result["remote"] is True
    assert result["transport"] == "p2p"
    assert result["peer_id"] == "node-gpu"
    assert result["node_id"] == "node-gpu"
    assert result["content"] == "remote hello over p2p"


@pytest.mark.asyncio
async def test_cluster_manager_auto_selects_local_when_it_matches():
    settings.cluster_enabled = True
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.cluster_request_timeout_ms = 5000
    settings.cluster_peers = "node-gpu|gpu|http://100.64.0.20:8100"

    manager = ClusterManager(router=_RouterLike(), agents_count_provider=lambda: 1)

    selection = await manager.select_route(
        peer_id=None,
        preferred_role=None,
        provider="ollama",
        model="llama3.2:3b",
        allow_local=True,
    )

    assert selection.selected_by == "auto-local"
    assert selection.remote is False
    assert selection.node_id == "node-1"


@pytest.mark.asyncio
async def test_cluster_manager_auto_selects_peer_by_role_and_model(monkeypatch):
    settings.cluster_enabled = True
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.cluster_request_timeout_ms = 5000
    settings.cluster_peers = "node-gpu|gpu|http://100.64.0.20:8100"

    manager = ClusterManager(router=_RouterLike(), agents_count_provider=lambda: 1)

    async def fake_probe(_peer):
        return type(
            "PeerStatusLike",
            (),
            {
                "peer_id": "node-gpu",
                "role": "gpu",
                "base_url": "http://100.64.0.20:8100",
                "ok": True,
                "status": 200,
                "latency_ms": 12,
                "error": None,
                "remote_node_id": "node-gpu",
                "remote_label": "GPU Node",
                "providers": ["ollama"],
                "provider_models": {"ollama": ["llama3.2:3b", "qwen2.5:7b"]},
                "agents": 16,
                "last_seen": "2026-03-07T12:00:00Z",
            },
        )()

    monkeypatch.setattr(manager, "_probe_peer", fake_probe)

    selection = await manager.select_route(
        peer_id=None,
        preferred_role="gpu",
        provider="ollama",
        model="qwen2.5:7b",
        allow_local=True,
    )

    assert selection.selected_by == "auto-peer"
    assert selection.remote is True
    assert selection.peer_id == "node-gpu"


@pytest.mark.asyncio
async def test_cluster_manager_merges_mdns_peers(monkeypatch):
    settings.cluster_enabled = True
    settings.cluster_mdns_enabled = True
    settings.cluster_mdns_advertise = False
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.cluster_request_timeout_ms = 5000
    settings.cluster_peers = "node-static|general|http://100.64.0.21:8100"
    settings.cluster_mdns_discovery_ttl_seconds = 60
    settings.mesh_bind_host = "100.64.0.10"

    manager = ClusterManager(router=_RouterLike(), agents_count_provider=lambda: 1)

    async def fake_discover_mdns():
        peers = [
            ClusterPeer(peer_id="node-mdns", role="edge", base_url="http://100.64.0.22:8100"),
        ]
        manager._mdns_peers = {peer.peer_id: peer for peer in peers}
        return peers

    async def fake_request_json(peer, method, path, *, json=None):
        if path == "/v1/cluster/node/identity":
            return {
                "node_id": peer.peer_id,
                "label": "remote",
                "providers": ["ollama"],
                "provider_models": {"ollama": ["qwen2.5:7b"]},
                "agents": 4,
            }
        return {}

    monkeypatch.setattr(manager, "_discover_mdns_peers", fake_discover_mdns)
    monkeypatch.setattr(manager, "_request_json", fake_request_json)

    peers = await manager.probe_peers()

    assert len(peers) == 2
    assert {peer.peer_id for peer in peers} == {"node-static", "node-mdns"}


@pytest.mark.asyncio
async def test_cluster_manager_explicit_send_can_target_discovered_mdns_peer(
    monkeypatch,
):
    settings.cluster_enabled = True
    settings.cluster_mdns_enabled = True
    settings.cluster_mdns_advertise = False
    settings.cluster_shared_key = SecretStr("cluster-key-123456")
    settings.node_id = "node-1"
    settings.node_role = "general"
    settings.node_label = "Node One"
    settings.cluster_request_timeout_ms = 5000
    settings.cluster_peers = ""
    settings.cluster_mdns_discovery_ttl_seconds = 60
    settings.mesh_bind_host = "100.64.0.10"

    manager = ClusterManager(router=_RouterLike(), agents_count_provider=lambda: 1)

    async def fake_discover_mdns():
        peers = [
            ClusterPeer(peer_id="node-mdns", role="edge", base_url="http://100.64.0.22:8100"),
        ]
        manager._mdns_peers = {peer.peer_id: peer for peer in peers}
        return peers

    async def fake_request_json(peer, method, path, *, json=None):
        assert peer.peer_id == "node-mdns"
        assert method == "POST"
        assert path == "/v1/cluster/node/send"
        return {
            "node_id": "node-mdns",
            "content": "ok",
            "model": "llama3.2:3b",
            "provider": "ollama",
            "usage": {},
        }

    monkeypatch.setattr(manager, "_discover_mdns_peers", fake_discover_mdns)
    monkeypatch.setattr(manager, "_request_json", fake_request_json)

    result = await manager.forward_send(
        peer_id="node-mdns",
        payload={
            "messages": [{"role": "user", "content": "hello"}],
            "strategy": "routellm",
            "routing_policy": "strong",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "system": None,
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    )

    assert result["remote"] is True
    assert result["peer_id"] == "node-mdns"
    assert result["node_id"] == "node-mdns"


def test_mdns_peer_matches_local_cluster_key():
    settings.cluster_shared_key = SecretStr("cluster-shared-key")
    assert _mdns_peer_matches_local_fingerprint(None) is False
    assert (
        _mdns_peer_matches_local_fingerprint(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        is False
    )
    assert (
        _mdns_peer_matches_local_fingerprint(
            "8f6dfcb3f9f4f6c1fdded4f0f4fae0d53e7e2e8cbe6e2e95f3f7dfc4a1f7f7a9"
        )
        is False
    )
    from hashlib import sha256

    expected = sha256(b"cluster-shared-key").hexdigest()
    assert _mdns_peer_matches_local_fingerprint(expected) is True
