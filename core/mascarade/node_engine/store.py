"""Node Store — Redis-backed persistence for DAG node catalog.

Provides NodeStore class for managing node catalog with Redis caching,
enabling distributed node engine coordination across cluster nodes.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis
from pydantic import BaseModel

logger = logging.getLogger("mascarade.node_engine.store")

# Redis key patterns
_CATALOG_KEY = "node:catalog"
_CATALOG_DOMAIN_KEY = "node:catalog:domain:{domain}"
_NODE_KEY = "node:{node_id}"
_METADATA_KEY = "node:metadata"


class NodeMetadata(BaseModel):
    """Metadata for a registered node."""

    node_id: str
    name: str
    domain: str
    description: str | None = None
    version: str = "1.0.0"
    tags: list[str] = []
    capabilities: dict[str, Any] = {}


class NodeStore:
    """Redis-backed node catalog store for distributed coordination.

    Provides thread-safe operations for:
    - Registering nodes with domain partitioning
    - Querying catalog (all nodes or by domain)
    - Caching metadata for fast retrieval
    - TTL-based expiration for stale entries
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        redis_url: str = "redis://localhost:6379/0",
        ttl_seconds: int = 3600,
    ) -> None:
        """
        Initialize NodeStore.

        Args:
            redis_client: Existing Redis client (if None, creates from url)
            redis_url: Redis connection URL (used if client is None)
            ttl_seconds: Default TTL for catalog entries (1 hour)
        """
        self.redis = redis_client or redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds
        logger.info(f"NodeStore initialized with TTL={ttl_seconds}s")

    def register_node(self, metadata: NodeMetadata) -> None:
        """
        Register a node in the catalog.

        Args:
            metadata: Node metadata to register
        """
        try:
            data = metadata.model_dump_json()

            # Store under node-specific key with TTL
            self.redis.setex(_NODE_KEY.format(node_id=metadata.node_id), self.ttl_seconds, data)

            # Add to catalog set (all nodes)
            self.redis.sadd(_CATALOG_KEY, metadata.node_id)

            # Add to domain-specific set
            domain_key = _CATALOG_DOMAIN_KEY.format(domain=metadata.domain)
            self.redis.sadd(domain_key, metadata.node_id)

            # Store metadata snapshot
            metadata_snapshot = {
                "node_id": metadata.node_id,
                "domain": metadata.domain,
                "name": metadata.name,
            }
            self.redis.hset(_METADATA_KEY, metadata.node_id, json.dumps(metadata_snapshot))

            logger.info(f"Registered node: {metadata.node_id} in domain: {metadata.domain}")
        except Exception as e:
            logger.error(f"Failed to register node {metadata.node_id}: {e}")
            raise

    def get_node(self, node_id: str) -> Optional[NodeMetadata]:
        """
        Retrieve node metadata by ID.

        Args:
            node_id: Node identifier

        Returns:
            NodeMetadata if found, None otherwise
        """
        try:
            data = self.redis.get(_NODE_KEY.format(node_id=node_id))
            if not data:
                return None
            return NodeMetadata.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to get node {node_id}: {e}")
            return None

    def list_all_nodes(self) -> list[NodeMetadata]:
        """
        List all registered nodes in the catalog.

        Returns:
            List of NodeMetadata objects (empty if none found)
        """
        try:
            node_ids = self.redis.smembers(_CATALOG_KEY)
            nodes = []
            for node_id in node_ids:
                node = self.get_node(node_id)
                if node:
                    nodes.append(node)
            logger.debug(f"Retrieved {len(nodes)} nodes from catalog")
            return nodes
        except Exception as e:
            logger.error(f"Failed to list all nodes: {e}")
            return []

    def list_nodes_by_domain(self, domain: str) -> list[NodeMetadata]:
        """
        List all nodes in a specific domain.

        Args:
            domain: Domain name to filter by

        Returns:
            List of NodeMetadata objects for the domain (empty if none)
        """
        try:
            domain_key = _CATALOG_DOMAIN_KEY.format(domain=domain)
            node_ids = self.redis.smembers(domain_key)
            nodes = []
            for node_id in node_ids:
                node = self.get_node(node_id)
                if node:
                    nodes.append(node)
            logger.debug(f"Retrieved {len(nodes)} nodes from domain: {domain}")
            return nodes
        except Exception as e:
            logger.error(f"Failed to list nodes for domain {domain}: {e}")
            return []

    def unregister_node(self, node_id: str) -> bool:
        """
        Unregister a node from the catalog.

        Args:
            node_id: Node identifier to remove

        Returns:
            True if removed, False if not found
        """
        try:
            node = self.get_node(node_id)
            if not node:
                return False

            # Remove from catalog
            self.redis.srem(_CATALOG_KEY, node_id)

            # Remove from domain set
            domain_key = _CATALOG_DOMAIN_KEY.format(domain=node.domain)
            self.redis.srem(domain_key, node_id)

            # Remove node data
            self.redis.delete(_NODE_KEY.format(node_id=node_id))

            # Remove metadata
            self.redis.hdel(_METADATA_KEY, node_id)

            logger.info(f"Unregistered node: {node_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unregister node {node_id}: {e}")
            return False

    def clear_catalog(self) -> None:
        """Clear all nodes from the catalog (use with caution)."""
        try:
            keys = self.redis.scan_iter(match="node:*")
            if keys:
                self.redis.delete(*keys)
            logger.warning("Cleared all nodes from catalog")
        except Exception as e:
            logger.error(f"Failed to clear catalog: {e}")

    def get_domain_list(self) -> list[str]:
        """
        Get list of all domains that have registered nodes.

        Returns:
            List of domain names
        """
        try:
            keys = self.redis.scan_iter(match="node:catalog:domain:*")
            domains = []
            for key in keys:
                domain = key.replace("node:catalog:domain:", "")
                domains.append(domain)
            return sorted(domains)
        except Exception as e:
            logger.error(f"Failed to get domain list: {e}")
            return []
