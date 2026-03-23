"""P2P metrics and observability — Prometheus counters and gauges."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.p2p.metrics")

try:
    from prometheus_client import Counter, Gauge, Histogram

    p2p_messages_sent = Counter(
        "mascarade_p2p_messages_sent_total",
        "Total P2P messages sent",
        ["message_type"],
    )
    p2p_messages_received = Counter(
        "mascarade_p2p_messages_received_total",
        "Total P2P messages received",
        ["message_type"],
    )
    p2p_connected_peers = Gauge(
        "mascarade_p2p_connected_peers",
        "Number of currently connected P2P peers",
    )
    p2p_dht_entries = Gauge(
        "mascarade_p2p_dht_entries",
        "Number of entries in the DHT routing table",
    )
    p2p_capabilities_known = Gauge(
        "mascarade_p2p_capabilities_known",
        "Number of peers with known capabilities",
    )
    p2p_forward_requests = Counter(
        "mascarade_p2p_forward_requests_total",
        "Total P2P stream forward requests",
        ["status"],  # success, error, timeout
    )
    p2p_forward_latency = Histogram(
        "mascarade_p2p_forward_latency_seconds",
        "P2P stream forward round-trip latency",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    p2p_bytes_sent = Counter(
        "mascarade_p2p_bytes_sent_total",
        "Total bytes sent over P2P transport",
    )
    p2p_bytes_received = Counter(
        "mascarade_p2p_bytes_received_total",
        "Total bytes received over P2P transport",
    )
    p2p_pubsub_messages = Counter(
        "mascarade_p2p_pubsub_messages_total",
        "Total PubSub messages published",
        ["topic"],
    )
    p2p_connection_errors = Counter(
        "mascarade_p2p_connection_errors_total",
        "Total P2P connection errors",
        ["peer_id"],
    )

    _PROMETHEUS_AVAILABLE = True

except ImportError:
    _PROMETHEUS_AVAILABLE = False


@dataclass
class P2PNodeMetrics:
    """In-memory metrics snapshot for P2P status endpoint."""

    peer_id: str = ""
    backend: str = "asyncio"
    uptime_seconds: float = 0.0
    connected_peers: int = 0
    dht_entries: int = 0
    capabilities_known: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    forward_requests_total: int = 0
    forward_errors: int = 0
    pubsub_topics: list[str] = field(default_factory=list)
    peer_details: list[dict] = field(default_factory=list)


class P2PMetricsCollector:
    """Collects and exposes P2P metrics."""

    def __init__(self, local_peer_id: str) -> None:
        self._local_peer_id = local_peer_id
        self._start_time = time.monotonic()
        self._lock = asyncio.Lock()
        self._messages_sent = 0
        self._messages_received = 0
        self._bytes_sent = 0
        self._bytes_received = 0
        self._forward_total = 0
        self._forward_errors = 0

    def record_message_sent(self, msg_type: str, size_bytes: int = 0) -> None:
        self._messages_sent += 1
        self._bytes_sent += size_bytes
        if _PROMETHEUS_AVAILABLE:
            p2p_messages_sent.labels(message_type=msg_type).inc()
            if size_bytes:
                p2p_bytes_sent.inc(size_bytes)

    def record_message_received(self, msg_type: str, size_bytes: int = 0) -> None:
        self._messages_received += 1
        self._bytes_received += size_bytes
        if _PROMETHEUS_AVAILABLE:
            p2p_messages_received.labels(message_type=msg_type).inc()
            if size_bytes:
                p2p_bytes_received.inc(size_bytes)

    def record_forward(self, status: str, latency_s: float = 0.0) -> None:
        self._forward_total += 1
        if status != "success":
            self._forward_errors += 1
        if _PROMETHEUS_AVAILABLE:
            p2p_forward_requests.labels(status=status).inc()
            if latency_s > 0:
                p2p_forward_latency.observe(latency_s)

    def record_pubsub(self, topic: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            p2p_pubsub_messages.labels(topic=topic).inc()

    def record_connection_error(self, peer_id: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            p2p_connection_errors.labels(peer_id=peer_id[:20]).inc()

    def update_gauges(
        self,
        connected_peers: int,
        dht_entries: int,
        capabilities_known: int,
    ) -> None:
        if _PROMETHEUS_AVAILABLE:
            p2p_connected_peers.set(connected_peers)
            p2p_dht_entries.set(dht_entries)
            p2p_capabilities_known.set(capabilities_known)

    def snapshot(
        self,
        connected_peers: int = 0,
        dht_entries: int = 0,
        capabilities_known: int = 0,
        pubsub_topics: list[str] | None = None,
        peer_details: list[dict] | None = None,
    ) -> P2PNodeMetrics:
        return P2PNodeMetrics(
            peer_id=self._local_peer_id,
            backend="asyncio",
            uptime_seconds=round(time.monotonic() - self._start_time, 1),
            connected_peers=connected_peers,
            dht_entries=dht_entries,
            capabilities_known=capabilities_known,
            messages_sent=self._messages_sent,
            messages_received=self._messages_received,
            bytes_sent=self._bytes_sent,
            bytes_received=self._bytes_received,
            forward_requests_total=self._forward_total,
            forward_errors=self._forward_errors,
            pubsub_topics=pubsub_topics or [],
            peer_details=peer_details or [],
        )
