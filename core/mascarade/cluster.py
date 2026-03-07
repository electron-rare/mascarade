"""Cluster primitives for static multi-node Mascarade deployments."""

from __future__ import annotations

import hmac
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mascarade.config import settings
from mascarade.router import Router

logger = logging.getLogger("mascarade.cluster")

_cluster_bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class ClusterPeer:
    peer_id: str
    role: str
    base_url: str


@dataclass(slots=True)
class NodeIdentity:
    node_id: str
    role: str
    label: str
    base_url: str | None
    providers: list[str]
    provider_models: dict[str, list[str]]
    agents: int
    cluster_enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "label": self.label,
            "base_url": self.base_url,
            "providers": self.providers,
            "provider_models": self.provider_models,
            "agents": self.agents,
            "cluster_enabled": self.cluster_enabled,
        }


@dataclass(slots=True)
class PeerStatus:
    peer_id: str
    role: str
    base_url: str
    ok: bool
    status: int
    latency_ms: int
    error: str | None = None
    remote_node_id: str | None = None
    remote_label: str | None = None
    providers: list[str] | None = None
    provider_models: dict[str, list[str]] | None = None
    agents: int | None = None
    last_seen: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "peer_id": self.peer_id,
            "role": self.role,
            "base_url": self.base_url,
            "ok": self.ok,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "remote_node_id": self.remote_node_id,
            "remote_label": self.remote_label,
            "providers": self.providers,
            "provider_models": self.provider_models,
            "agents": self.agents,
            "last_seen": self.last_seen,
        }


@dataclass(slots=True)
class ClusterRouteSelection:
    selected_by: str
    remote: bool
    peer_id: str | None
    node_id: str
    role: str
    base_url: str | None


def _normalized_url(value: str) -> str:
    return value.strip().rstrip("/")


def advertised_base_url() -> str | None:
    if not settings.cluster_enabled or not settings.mesh_bind_host.strip():
        return None
    return f"{settings.mesh_scheme}://{settings.mesh_bind_host.strip()}:{settings.core_port}"


def parse_cluster_peers(raw: str, *, node_id: str) -> list[ClusterPeer]:
    peers: list[ClusterPeer] = []
    seen: set[str] = set()
    entries = [chunk.strip() for chunk in raw.split(";") if chunk.strip()]
    for entry in entries:
        parts = [part.strip() for part in entry.split("|")]
        if len(parts) != 3:
            logger.warning("Ignoring invalid CLUSTER_PEERS entry: %s", entry)
            continue

        peer_id, role, base_url = parts
        if not peer_id or not role or not base_url:
            logger.warning("Ignoring incomplete CLUSTER_PEERS entry: %s", entry)
            continue
        if peer_id == node_id:
            logger.warning("Ignoring self peer entry for node_id=%s", node_id)
            continue
        if peer_id in seen:
            raise ValueError(f"Duplicate cluster peer id: {peer_id}")

        normalized_url = _normalized_url(base_url)
        parsed = urlparse(normalized_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            logger.warning("Ignoring invalid peer URL for %s: %s", peer_id, base_url)
            continue

        peers.append(ClusterPeer(peer_id=peer_id, role=role, base_url=normalized_url))
        seen.add(peer_id)
    return peers


async def require_cluster_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_cluster_bearer),
) -> None:
    if not settings.cluster_enabled:
        raise HTTPException(status_code=503, detail="Cluster disabled")

    key = settings.cluster_shared_key.strip()
    if not key:
        raise HTTPException(status_code=503, detail="Cluster not configured")

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing cluster token")

    candidate = credentials.credentials.strip()
    if not candidate or not hmac.compare_digest(candidate.encode(), key.encode()):
        raise HTTPException(status_code=401, detail="Invalid cluster token")


class ClusterManager:
    """Static peer inventory and first-hop core-to-core forwarding."""

    def __init__(self, *, router: Router, agents_count_provider) -> None:
        self._router = router
        self._agents_count_provider = agents_count_provider
        self._timeout_s = max(settings.cluster_request_timeout_ms, 500) / 1000
        self._peers = parse_cluster_peers(settings.cluster_peers, node_id=settings.node_id)

    @property
    def enabled(self) -> bool:
        return bool(settings.cluster_enabled)

    @property
    def peers(self) -> list[ClusterPeer]:
        return list(self._peers)

    def local_identity(self) -> NodeIdentity:
        provider_models = (
            self._router.provider_model_map()
            if hasattr(self._router, "provider_model_map")
            else {name: [] for name in self._router.available_providers}
        )
        return NodeIdentity(
            node_id=settings.node_id,
            role=settings.node_role,
            label=settings.node_label,
            base_url=advertised_base_url(),
            providers=self._router.available_providers,
            provider_models=provider_models,
            agents=self._agents_count_provider(),
            cluster_enabled=self.enabled,
        )

    async def probe_peers(self) -> list[PeerStatus]:
        statuses: list[PeerStatus] = []
        for peer in self._peers:
            statuses.append(await self._probe_peer(peer))
        return statuses

    async def forward_send(
        self,
        *,
        peer_id: str | None = None,
        preferred_role: str | None = None,
        allow_local: bool = True,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if not settings.cluster_forward_enabled:
            raise HTTPException(status_code=403, detail="Cluster forwarding disabled")
        selection = await self.select_route(
            peer_id=peer_id,
            preferred_role=preferred_role,
            provider=self._coerce_optional_string(payload.get("provider")),
            model=self._coerce_optional_string(payload.get("model")),
            allow_local=allow_local,
        )

        if not selection.remote:
            logger.info("cluster auto/local send -> %s", selection.node_id)
            response = await self._send_local(payload)
            return {
                "peer_id": None,
                "selected_by": selection.selected_by,
                "remote": False,
                "latency_ms": 0,
                "node_id": selection.node_id,
                "role": selection.role,
                **response,
            }

        if selection.peer_id is None:
            raise HTTPException(status_code=500, detail="Cluster route selection failed")

        peer = next((candidate for candidate in self._peers if candidate.peer_id == selection.peer_id), None)
        if peer is None:
            raise HTTPException(status_code=404, detail=f"Unknown cluster peer: {selection.peer_id}")

        logger.info("cluster forward send -> %s", peer.peer_id)
        started = time.perf_counter()
        remote = await self._request_json(peer, "POST", "/cluster/node/send", json=payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info("cluster forward send <- %s (%d ms)", peer.peer_id, latency_ms)
        return {
            "peer_id": peer.peer_id,
            "selected_by": selection.selected_by,
            "remote": True,
            "latency_ms": latency_ms,
            "role": selection.role,
            **remote,
        }

    async def select_route(
        self,
        *,
        peer_id: str | None,
        preferred_role: str | None,
        provider: str | None,
        model: str | None,
        allow_local: bool,
    ) -> ClusterRouteSelection:
        if peer_id:
            peer = next((candidate for candidate in self._peers if candidate.peer_id == peer_id), None)
            if peer is None:
                raise HTTPException(status_code=404, detail=f"Unknown cluster peer: {peer_id}")
            return ClusterRouteSelection(
                selected_by="explicit-peer",
                remote=True,
                peer_id=peer.peer_id,
                node_id=peer.peer_id,
                role=peer.role,
                base_url=peer.base_url,
            )

        local = self.local_identity()
        peer_statuses = await self.probe_peers()
        remote_candidates = [peer for peer in peer_statuses if peer.ok]

        if preferred_role:
            if allow_local and local.role == preferred_role and self._identity_matches(local, provider=provider, model=model):
                return ClusterRouteSelection(
                    selected_by="auto-local",
                    remote=False,
                    peer_id=None,
                    node_id=local.node_id,
                    role=local.role,
                    base_url=local.base_url,
                )
            remote_candidates = [peer for peer in remote_candidates if peer.role == preferred_role]

        matching_remote = [
            peer
            for peer in remote_candidates
            if self._peer_matches(peer, provider=provider, model=model)
        ]

        if allow_local and self._identity_matches(local, provider=provider, model=model):
            return ClusterRouteSelection(
                selected_by="auto-local",
                remote=False,
                peer_id=None,
                node_id=local.node_id,
                role=local.role,
                base_url=local.base_url,
            )

        if matching_remote:
            best_remote = sorted(
                matching_remote,
                key=lambda peer: (peer.latency_ms, peer.peer_id),
            )[0]
            return ClusterRouteSelection(
                selected_by="auto-peer",
                remote=True,
                peer_id=best_remote.peer_id,
                node_id=best_remote.remote_node_id or best_remote.peer_id,
                role=best_remote.role,
                base_url=best_remote.base_url,
            )

        if remote_candidates and not provider and not model and not preferred_role:
            best_remote = sorted(
                remote_candidates,
                key=lambda peer: (peer.latency_ms, peer.peer_id),
            )[0]
            return ClusterRouteSelection(
                selected_by="auto-peer-fallback",
                remote=True,
                peer_id=best_remote.peer_id,
                node_id=best_remote.remote_node_id or best_remote.peer_id,
                role=best_remote.role,
                base_url=best_remote.base_url,
            )

        raise HTTPException(
            status_code=404,
            detail="No cluster route matched the requested provider/model/role",
        )

    async def _probe_peer(self, peer: ClusterPeer) -> PeerStatus:
        started = time.perf_counter()
        try:
            remote = await self._request_json(peer, "GET", "/cluster/node/identity")
        except HTTPException as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return PeerStatus(
                peer_id=peer.peer_id,
                role=peer.role,
                base_url=peer.base_url,
                ok=False,
                status=exc.status_code,
                latency_ms=latency_ms,
                error=str(exc.detail),
            )
        except Exception as exc:  # pragma: no cover - defensive
            latency_ms = int((time.perf_counter() - started) * 1000)
            return PeerStatus(
                peer_id=peer.peer_id,
                role=peer.role,
                base_url=peer.base_url,
                ok=False,
                status=0,
                latency_ms=latency_ms,
                error=str(exc),
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        return PeerStatus(
            peer_id=peer.peer_id,
            role=peer.role,
            base_url=peer.base_url,
            ok=True,
            status=200,
            latency_ms=latency_ms,
            remote_node_id=str(remote.get("node_id") or ""),
            remote_label=str(remote.get("label") or ""),
            providers=list(remote.get("providers") or []),
            provider_models=self._coerce_provider_models(remote.get("provider_models")),
            agents=int(remote.get("agents") or 0),
            last_seen=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    async def _send_local(self, payload: dict[str, object]) -> dict[str, object]:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="Cluster local send requires messages")

        try:
            response = await self._router.send(
                messages,
                strategy=payload.get("strategy", "best"),
                provider=self._coerce_optional_string(payload.get("provider")),
                model=self._coerce_optional_string(payload.get("model")),
                system=self._coerce_optional_string(payload.get("system")),
                temperature=float(payload.get("temperature", 0.7)),
                max_tokens=int(payload.get("max_tokens", 4096)),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid request parameters") from exc

        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }

    @staticmethod
    def _coerce_optional_string(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _coerce_provider_models(value: object) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            return {}
        mapped: dict[str, list[str]] = {}
        for provider, models in value.items():
            if not isinstance(provider, str):
                continue
            if isinstance(models, list):
                mapped[provider] = [str(model) for model in models if isinstance(model, str)]
        return mapped

    @staticmethod
    def _identity_matches(identity: NodeIdentity, *, provider: str | None, model: str | None) -> bool:
        if provider and provider not in identity.providers:
            return False
        if model:
            if provider:
                return model in identity.provider_models.get(provider, [])
            return any(model in models for models in identity.provider_models.values())
        return True

    @staticmethod
    def _peer_matches(peer: PeerStatus, *, provider: str | None, model: str | None) -> bool:
        peer_providers = peer.providers or []
        peer_models = peer.provider_models or {}
        if provider and provider not in peer_providers:
            return False
        if model:
            if provider:
                return model in peer_models.get(provider, [])
            return any(model in models for models in peer_models.values())
        return True

    async def _request_json(
        self,
        peer: ClusterPeer,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
    ) -> dict[str, object]:
        url = f"{peer.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {settings.cluster_shared_key.strip()}",
            "X-Mascarade-Node-ID": settings.node_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.request(method, url, json=json, headers=headers)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=502, detail=f"Cluster peer timed out: {peer.peer_id}") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Cluster peer unreachable: {peer.peer_id}") from exc

        if response.status_code in {401, 403}:
            raise HTTPException(status_code=502, detail=f"Cluster auth failed for peer: {peer.peer_id}")
        if not response.is_success:
            body = response.text.strip() or f"HTTP {response.status_code}"
            raise HTTPException(status_code=502, detail=f"Cluster peer error {peer.peer_id}: {body}")

        parsed = response.json()
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=502, detail=f"Cluster peer invalid JSON: {peer.peer_id}")
        return parsed
