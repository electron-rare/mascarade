"""Cluster primitives for static multi-node Mascarade deployments."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from socket import AF_INET, AF_INET6, inet_aton, inet_ntop
from urllib.parse import urlparse
from typing import Any

import socket

try:
    from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
except Exception:  # pragma: no cover - optional dependency
    ServiceBrowser = None
    ServiceInfo = None
    ServiceListener = object
    Zeroconf = None

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mascarade.config import settings
from mascarade.router import Router

try:
    from mascarade.p2p.node import P2PNode, P2PPeer
except Exception:  # pragma: no cover - optional dependency
    P2PNode = None  # type: ignore[assignment, misc]
    P2PPeer = None  # type: ignore[assignment, misc]

logger = logging.getLogger("mascarade.cluster")

_cluster_bearer = HTTPBearer(auto_error=False)

_DEFAULT_MDNS_SERVICE = "_mascarade._tcp.local."
_DEFAULT_MDNS_DISCOVERY_TTL_SECONDS = 60


def _mdns_service_type(raw: str) -> str:
    service = (raw or _DEFAULT_MDNS_SERVICE).strip()
    if not service:
        return _DEFAULT_MDNS_SERVICE

    if not service.endswith("."):
        service = f"{service}."

    if ".local." not in service:
        service = f"{service.rstrip('.')}._tcp.local."
    return service


class _ClusterMdnsDiscoveryListener(ServiceListener):
    def __init__(self) -> None:
        self._services: set[str] = set()

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:  # noqa: ARG002
        self._services.add(name)

    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:  # noqa: ARG002
        self._services.discard(name)

    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:  # noqa: ARG002
        self._services.add(name)

    @property
    def services(self) -> set[str]:
        return set(self._services)


def _cluster_mdns_enabled() -> bool:
    return bool(
        settings.cluster_enabled
        and settings.cluster_mdns_enabled
        and ServiceBrowser
        and ServiceInfo
        and Zeroconf
    )


def _safe_listen_host() -> str:
    host = settings.mesh_bind_host.strip()
    return host


def _mdns_key_fingerprint() -> str:
    key = settings.cluster_shared_key.strip().encode("utf-8")
    if not key:
        return ""
    return hashlib.sha256(key).hexdigest()


def _mdns_peer_matches_local_fingerprint(peer_fingerprint: str | None) -> bool:
    local_fingerprint = _mdns_key_fingerprint()
    if not local_fingerprint:
        return True
    if not peer_fingerprint:
        logger.warning("mDNS peer rejected: missing cluster key fingerprint in TXT")
        return False
    if peer_fingerprint != local_fingerprint:
        logger.warning("mDNS peer rejected: cluster key fingerprint mismatch")
        return False
    return True


def _normalize_txt_records(raw_props: Any) -> dict[str, str]:
    props: dict[str, str] = {}
    if raw_props is None:
        return props

    if isinstance(raw_props, dict):
        for key, value in raw_props.items():
            if key is None:
                continue
            if isinstance(value, bytes):
                try:
                    decoded = value.decode("utf-8")
                except UnicodeDecodeError:
                    decoded = value.decode("utf-8", errors="ignore")
            else:
                decoded = str(value)
            props[str(key).strip()] = decoded.strip()
        return props

    return props


def _ip_from_host(host: str) -> tuple[bytes, int] | tuple[None, None]:
    """Return packed binary IP and family for zeroconf."""
    host = host.strip()
    if not host:
        return None, 0

    try:
        return inet_aton(host), AF_INET
    except OSError:
        pass

    try:
        return socket.inet_pton(AF_INET6, host), AF_INET6
    except OSError:
        return None, 0


def _parsed_addresses(info: Any) -> list[str]:
    addresses: list[str] = []
    if info is None:
        return addresses

    try:
        parsed = list(info.parsed_addresses())
        if parsed:
            return parsed
    except Exception:  # pragma: no cover - optional zeroconf layout
        pass

    try:
        for raw in info.addresses:
            if isinstance(raw, bytes):
                if len(raw) == 4:
                    addresses.append(inet_ntop(AF_INET, raw))
                elif len(raw) == 16:
                    addresses.append(inet_ntop(AF_INET6, raw))
            elif isinstance(raw, str):
                addresses.append(raw)
    except Exception:  # pragma: no cover - optional zeroconf layout
        pass
    return addresses


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
    """Cluster manager with optional mDNS peer discovery."""

    def __init__(self, *, router: Router, agents_count_provider) -> None:
        self._router = router
        self._agents_count_provider = agents_count_provider
        self._timeout_s = max(settings.cluster_request_timeout_ms, 500) / 1000
        self._peers = parse_cluster_peers(settings.cluster_peers, node_id=settings.node_id)
        self._mdns_peers: dict[str, ClusterPeer] = {}
        self._mdns_discovery_expiry = 0.0
        self._mdns_advertiser: Zeroconf | None = None
        self._mdns_service_info: ServiceInfo | None = None
        self._p2p_node: P2PNode | None = None  # type: ignore[valid-type]

        if _cluster_mdns_enabled() and settings.cluster_mdns_advertise:
            self._register_mdns_service()

    @property
    def enabled(self) -> bool:
        return bool(settings.cluster_enabled)

    @property
    def peers(self) -> list[ClusterPeer]:
        return list(self._collect_known_peers())

    # ── P2P lifecycle (called from server lifespan) ───────────────────

    def _p2p_enabled(self) -> bool:
        return bool(settings.p2p_enabled and P2PNode is not None)

    async def start_p2p(self) -> None:
        """Start the libp2p P2P node if enabled."""
        if not self._p2p_enabled():
            return
        try:
            self._p2p_node = P2PNode(settings)
            await self._p2p_node.start(
                identity_provider=lambda: self.local_identity().to_dict(),
                send_handler=self._p2p_local_send,
            )
            logger.info(
                "P2P node started — peer_id=%s", self._p2p_node.peer_id
            )
        except Exception as exc:
            logger.warning("P2P node failed to start: %s", exc)
            self._p2p_node = None

    async def stop_p2p(self) -> None:
        """Stop the libp2p P2P node."""
        if self._p2p_node:
            await self._p2p_node.stop()
            self._p2p_node = None

    def _p2p_local_send(self, payload: dict) -> dict:
        """Synchronous wrapper for local send, called from trio thread."""
        import asyncio as _asyncio

        loop = _asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._send_local(payload))
        finally:
            loop.close()

    def p2p_status(self) -> dict:
        """Return P2P diagnostic info."""
        if self._p2p_node:
            return self._p2p_node.status()
        return {"running": False, "reason": "disabled" if not self._p2p_enabled() else "not started"}

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

    def _collect_known_peers(self) -> list[ClusterPeer]:
        peers_by_id: dict[str, ClusterPeer] = {}
        for peer in parse_cluster_peers(settings.cluster_peers, node_id=settings.node_id):
            peers_by_id[peer.peer_id] = peer

        for peer in self._mdns_peers.values():
            if peer.peer_id not in peers_by_id and peer.peer_id != settings.node_id:
                peers_by_id[peer.peer_id] = peer

        # Merge libp2p-discovered peers
        if self._p2p_node:
            for p2p_peer in self._p2p_node.discovered_peers():
                if p2p_peer.peer_id not in peers_by_id and p2p_peer.peer_id != settings.node_id:
                    peers_by_id[p2p_peer.peer_id] = ClusterPeer(
                        peer_id=p2p_peer.peer_id,
                        role=p2p_peer.role,
                        base_url=p2p_peer.base_url,
                    )

        return list(peers_by_id.values())

    def _mdns_discovery_ttl(self) -> float:
        try:
            ttl = int(settings.cluster_mdns_discovery_ttl_seconds)
        except (TypeError, ValueError):
            ttl = 60

        if ttl < 5:
            return 5.0
        if ttl > 300:
            return 300.0
        return float(ttl)

    def _mdns_discovery_scan_timeout(self) -> float:
        timeout = self._mdns_discovery_ttl() / 6
        if timeout < 0.5:
            return 0.5
        if timeout > 2.5:
            return 2.5
        return timeout

    async def _discover_mdns_peers(self) -> list[ClusterPeer]:
        now = time.monotonic()
        if now < self._mdns_discovery_expiry:
            return self._collect_mdns_peers_cached()

        return await asyncio.to_thread(self._discover_mdns_peers_sync)

    def _collect_mdns_peers_cached(self) -> list[ClusterPeer]:
        return list(self._mdns_peers.values())

    def _mdns_service_name(self) -> str:
        return f"{settings.node_id}.{_mdns_service_type(settings.cluster_mdns_service)}"

    def _mdns_txt(self) -> dict[str, str]:
        records = {
            "node_id": settings.node_id,
            "role": settings.node_role,
            "label": settings.node_label,
            "scheme": settings.mesh_scheme,
            "core_port": str(settings.core_port),
            "mesh_bind_host": settings.mesh_bind_host,
        }
        fingerprint = _mdns_key_fingerprint()
        if fingerprint:
            records["cluster_key_fingerprint"] = fingerprint
        return records

    def _register_mdns_service(self) -> None:
        if not _cluster_mdns_enabled() or not settings.cluster_mdns_advertise:
            return

        host = _safe_listen_host()
        if not host:
            logger.warning("Cannot register mDNS service: MESH_BIND_HOST missing")
            return

        service_type = _mdns_service_type(settings.cluster_mdns_service)
        service_name = self._mdns_service_name()
        ip_bytes, _ = _ip_from_host(host)
        if ip_bytes is None:
            logger.warning("Cannot register mDNS service: invalid MESH_BIND_HOST=%s", host)
            return

        properties = {
            key: value.encode("utf-8") for key, value in self._mdns_txt().items()
        }

        try:
            addresses: list[bytes] = [ip_bytes]
            self._mdns_service_info = ServiceInfo(
                type_=service_type,
                name=service_name,
                addresses=addresses,
                port=settings.core_port,
                properties=properties,
                server=f"{settings.node_id}.local.",
            )
            self._mdns_advertiser = Zeroconf()
            assert self._mdns_advertiser is not None
            assert self._mdns_service_info is not None
            self._mdns_advertiser.register_service(self._mdns_service_info)
            logger.info("mDNS service advertised: name=%s type=%s", service_name, service_type)
        except Exception as exc:
            self._mdns_advertiser = None
            self._mdns_service_info = None
            logger.warning("mDNS service registration failed: %s", exc)

    def _discover_mdns_peers_sync(self) -> list[ClusterPeer]:
        if not _cluster_mdns_enabled():
            self._mdns_discovery_expiry = time.monotonic() + 1.0
            self._mdns_peers = {}
            return []

        service_type = _mdns_service_type(settings.cluster_mdns_service)
        listener = _ClusterMdnsDiscoveryListener()
        zc = Zeroconf()
        browser = ServiceBrowser(zc, service_type, listener)
        deadline = time.monotonic() + self._mdns_discovery_scan_timeout()
        try:
            while time.monotonic() < deadline:
                time.sleep(0.1)
            discovered: list[ClusterPeer] = []
            for name in sorted(listener.services):
                info = zc.get_service_info(service_type, name)
                peer = self._parse_mdns_peer(name, info)
                if peer is not None:
                    discovered.append(peer)
            self._mdns_peers = {peer.peer_id: peer for peer in discovered}
            self._mdns_discovery_expiry = time.monotonic() + self._mdns_discovery_ttl()
            return discovered
        except Exception as exc:  # pragma: no cover - optional dependency/OS discovery failures
            logger.warning("mDNS peer discovery failed: %s", exc)
            self._mdns_peers = {}
            return []
        finally:
            try:
                browser.cancel()
            except Exception:  # pragma: no cover
                pass
            try:
                zc.close()
            except Exception:  # pragma: no cover
                pass

    @staticmethod
    def _parse_mdns_peer(service_name: str, info: Any) -> ClusterPeer | None:
        txt = _normalize_txt_records(getattr(info, "properties", {}))
        peer_id = txt.get("node_id") or service_name.split(".")[0].strip()
        if not peer_id or peer_id == settings.node_id:
            return None

        peer_fingerprint = txt.get("cluster_key_fingerprint")
        if not _mdns_peer_matches_local_fingerprint(peer_fingerprint):
            return None

        role = txt.get("role") or "general"
        scheme = (txt.get("scheme") or settings.mesh_scheme).strip()
        if scheme not in {"http", "https"}:
            scheme = settings.mesh_scheme.strip() or "http"

        port = txt.get("core_port") or txt.get("port") or str(settings.core_port)
        try:
            parsed_port = int(port)
        except (TypeError, ValueError):
            parsed_port = settings.core_port

        host = txt.get("mesh_bind_host")
        if not host:
            addresses = _parsed_addresses(info)
            if addresses:
                host = addresses[0]
        if not host:
            host = "127.0.0.1"

        base_url = _normalized_url(f"{scheme}://{host}:{parsed_port}")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return ClusterPeer(peer_id=peer_id, role=role, base_url=base_url)

    async def probe_peers(self) -> list[PeerStatus]:
        await self._discover_mdns_peers()
        self._peers = self._collect_known_peers()

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

        peers = self._collect_known_peers()
        peer = next((candidate for candidate in peers if candidate.peer_id == selection.peer_id), None)
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
        peers = self._collect_known_peers()
        await self._discover_mdns_peers()
        peers = self._collect_known_peers()
        if peer_id:
            peer = next((candidate for candidate in peers if candidate.peer_id == peer_id), None)
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
        peer_statuses = []
        for peer in peers:
            peer_statuses.append(await self._probe_peer(peer))
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
