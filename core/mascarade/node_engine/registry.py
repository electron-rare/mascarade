"""Node type and worker registries (minimal stub for Phase 3).

Full implementation in Phase 5.
"""

from __future__ import annotations


class NodeTypeRegistry:
    """Stub registry for node types. Full implementation in Phase 5."""

    def __init__(self) -> None:
        self._types: dict[str, object] = {}


class WorkerRegistry:
    """Stub registry for workers. Full implementation in Phase 5."""

    def __init__(self) -> None:
        self._workers: dict[str, object] = {}
