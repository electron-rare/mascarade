"""Worker interface for Node Engine — base class for domain-specific node workers."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass


@dataclass
class WorkerCapabilities:
    """Capabilities and constraints for a node worker."""

    max_concurrent: int
    timeout_default_s: int
    requires_runtime: bool = False
    runtime_check_endpoint: str | None = None

    def __post_init__(self) -> None:
        """Validate capabilities configuration."""
        if self.max_concurrent <= 0:
            raise ValueError("max_concurrent must be positive")
        if self.timeout_default_s <= 0:
            raise ValueError("timeout_default_s must be positive")
        if self.requires_runtime and not self.runtime_check_endpoint:
            raise ValueError(
                "runtime_check_endpoint is required when requires_runtime is True"
            )


class NodeWorker(ABC):
    """Abstract base class for node workers.

    Workers register domain-specific nodes with the Node Engine.
    Each worker defines its capabilities and the node types it provides.
    """

    domain: str
    name: str
    version: str
    capabilities: WorkerCapabilities
    node_types: list[str]

    def __init_subclass__(cls) -> None:
        """Validate that subclasses define required class attributes."""
        required_attrs = ["domain", "name", "version", "capabilities", "node_types"]
        for attr in required_attrs:
            if not hasattr(cls, attr):
                raise TypeError(
                    f"NodeWorker subclass {cls.__name__} must define '{attr}' class attribute"
                )
