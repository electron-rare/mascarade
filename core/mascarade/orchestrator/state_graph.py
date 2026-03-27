"""LangGraph-inspired stateful graph execution with checkpointing.

Self-contained implementation — no dependency on the langgraph package.
Each node is an async (or sync) callable that receives the current state dict
and returns a partial dict merged back into state.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("mascarade.orchestrator.state_graph")

# Sentinel used as the target for finish edges.
END = "__end__"

# Default upper bound on node executions to prevent infinite loops.
_DEFAULT_MAX_ITERATIONS = 25


class GraphExecutionError(Exception):
    """Raised when the graph cannot complete."""


class StateGraph:
    """LangGraph-inspired stateful graph execution with checkpointing.

    Usage::

        graph = StateGraph()
        graph.add_node("classify", classify_fn)
        graph.add_node("handle_a", handle_a_fn)
        graph.add_node("handle_b", handle_b_fn)
        graph.add_conditional_edges(
            "classify",
            lambda s: s["category"],
            {"a": "handle_a", "b": "handle_b"},
        )
        graph.set_entry_point("classify")
        graph.set_finish_point("handle_a")
        graph.set_finish_point("handle_b")
        result = await graph.invoke({"text": "hello"})
    """

    def __init__(
        self,
        state_schema: type[BaseModel] | None = None,
        *,
        checkpoint_dir: str | None = None,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self.state_schema = state_schema
        self.checkpoint_dir = checkpoint_dir
        self.max_iterations = max_iterations

        self._nodes: dict[str, Callable[..., Any]] = {}
        self._edges: dict[str, list[str]] = {}  # source -> [targets]
        self._conditional_edges: dict[
            str, list[tuple[Callable[..., Any], dict[str, str]]]
        ] = {}
        self._entry_point: str | None = None
        self._finish_points: set[str] = set()

    # ------------------------------------------------------------------
    # Builder API
    # ------------------------------------------------------------------

    def add_node(self, name: str, fn: Callable[..., Any]) -> StateGraph:
        """Register a node.  *fn* can be sync or async."""
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already exists")
        if name == END:
            raise ValueError(f"'{END}' is reserved")
        self._nodes[name] = fn
        return self

    def add_edge(self, source: str, target: str) -> StateGraph:
        """Add an unconditional edge from *source* to *target*."""
        self._edges.setdefault(source, []).append(target)
        return self

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable[..., str],
        mapping: dict[str, str],
    ) -> StateGraph:
        """Add conditional branching from *source*.

        *condition* receives the current state dict and must return a key
        present in *mapping*.  The value in *mapping* is the next node name
        (or ``END``).
        """
        self._conditional_edges.setdefault(source, []).append(
            (condition, mapping)
        )
        return self

    def set_entry_point(self, name: str) -> StateGraph:
        self._entry_point = name
        return self

    def set_finish_point(self, name: str) -> StateGraph:
        """Mark *name* as a terminal node (implicit edge to END)."""
        self._finish_points.add(name)
        return self

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if self._entry_point is None:
            raise GraphExecutionError("No entry point set")
        if self._entry_point not in self._nodes:
            raise GraphExecutionError(
                f"Entry point '{self._entry_point}' is not a registered node"
            )
        for src, targets in self._edges.items():
            if src not in self._nodes:
                raise GraphExecutionError(
                    f"Edge source '{src}' is not a registered node"
                )
            for t in targets:
                if t != END and t not in self._nodes:
                    raise GraphExecutionError(
                        f"Edge target '{t}' is not a registered node"
                    )
        for src in self._conditional_edges:
            if src not in self._nodes:
                raise GraphExecutionError(
                    f"Conditional edge source '{src}' is not a registered node"
                )

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _validate_state(self, state: dict[str, Any]) -> None:
        if self.state_schema is not None:
            self.state_schema.model_validate(state)

    @staticmethod
    def _merge(state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(state)
        merged.update(updates)
        return merged

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def _checkpoint_path(self, run_id: str) -> str | None:
        if self.checkpoint_dir is None:
            return None
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        return os.path.join(self.checkpoint_dir, f"{run_id}.json")

    def _save_checkpoint(
        self,
        run_id: str,
        state: dict[str, Any],
        current_node: str,
        iteration: int,
    ) -> None:
        path = self._checkpoint_path(run_id)
        if path is None:
            return
        payload = {
            "run_id": run_id,
            "state": state,
            "current_node": current_node,
            "iteration": iteration,
            "timestamp": time.time(),
        }
        with open(path, "w") as fp:
            json.dump(payload, fp, default=str)
        logger.debug("Checkpoint saved: %s (node=%s, iter=%d)", run_id, current_node, iteration)

    def load_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Load a previously saved checkpoint.  Returns ``None`` if absent."""
        path = self._checkpoint_path(run_id)
        if path is None or not os.path.exists(path):
            return None
        with open(path) as fp:
            return json.load(fp)

    # ------------------------------------------------------------------
    # Resolution: which node comes next?
    # ------------------------------------------------------------------

    def _resolve_next(self, current: str, state: dict[str, Any]) -> str | None:
        """Determine the next node after *current*.

        Priority: conditional edges first, then unconditional edges.
        Returns ``None`` when the graph should stop.
        """
        # Conditional edges
        conds = self._conditional_edges.get(current, [])
        for condition_fn, mapping in conds:
            if asyncio.iscoroutinefunction(condition_fn):
                raise GraphExecutionError(
                    "Async condition functions are not supported in _resolve_next; "
                    "use _resolve_next_async instead."
                )
            key = condition_fn(state)
            target = mapping.get(key)
            if target is None:
                raise GraphExecutionError(
                    f"Condition on '{current}' returned '{key}' which is not in mapping {list(mapping.keys())}"
                )
            if target == END:
                return None
            return target

        # Unconditional edges
        targets = self._edges.get(current, [])
        if targets:
            target = targets[0]
            return None if target == END else target

        # Finish point
        if current in self._finish_points:
            return None

        # No outgoing edge and not a finish point — dead end
        return None

    async def _resolve_next_async(
        self, current: str, state: dict[str, Any]
    ) -> str | None:
        """Async variant of _resolve_next (supports async condition fns)."""
        conds = self._conditional_edges.get(current, [])
        for condition_fn, mapping in conds:
            if asyncio.iscoroutinefunction(condition_fn):
                key = await condition_fn(state)
            else:
                key = condition_fn(state)
            target = mapping.get(key)
            if target is None:
                raise GraphExecutionError(
                    f"Condition on '{current}' returned '{key}' which is not in mapping {list(mapping.keys())}"
                )
            if target == END:
                return None
            return target

        targets = self._edges.get(current, [])
        if targets:
            target = targets[0]
            return None if target == END else target

        if current in self._finish_points:
            return None

        return None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _call_node(
        self, name: str, state: dict[str, Any]
    ) -> dict[str, Any]:
        fn = self._nodes[name]
        if inspect.iscoroutinefunction(fn):
            result = await fn(state)
        else:
            result = fn(state)
        if result is None:
            return {}
        if not isinstance(result, dict):
            raise GraphExecutionError(
                f"Node '{name}' must return a dict or None, got {type(result).__name__}"
            )
        return result

    async def invoke(
        self,
        state: dict[str, Any],
        *,
        config: dict[str, Any] | None = None,
        run_id: str | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        """Execute the graph from entry to finish and return final state.

        Parameters
        ----------
        state:
            Initial state dict.
        config:
            Optional configuration dict (currently passed through state as
            ``__config__`` if provided).
        run_id:
            Unique identifier for this execution.  Auto-generated if omitted.
        resume:
            If *True*, try to resume from an existing checkpoint for *run_id*.
        """
        self._validate()
        run_id = run_id or uuid.uuid4().hex
        config = config or {}

        current_node: str | None = self._entry_point
        iteration = 0

        # Resume support
        if resume:
            checkpoint = self.load_checkpoint(run_id)
            if checkpoint is not None:
                state = checkpoint["state"]
                current_node = checkpoint["current_node"]
                iteration = checkpoint["iteration"]
                logger.info(
                    "Resuming run %s from node '%s' (iter=%d)",
                    run_id,
                    current_node,
                    iteration,
                )

        self._validate_state(state)

        while current_node is not None:
            if iteration >= self.max_iterations:
                raise GraphExecutionError(
                    f"Max iterations ({self.max_iterations}) exceeded — possible infinite loop"
                )

            updates = await self._call_node(current_node, state)
            state = self._merge(state, updates)
            iteration += 1

            self._save_checkpoint(run_id, state, current_node, iteration)

            current_node = await self._resolve_next_async(current_node, state)

        return state

    async def stream(
        self,
        state: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Yield ``(node_name, updated_state)`` tuples as the graph executes."""
        self._validate()
        run_id = run_id or uuid.uuid4().hex

        current_node: str | None = self._entry_point
        iteration = 0

        self._validate_state(state)

        while current_node is not None:
            if iteration >= self.max_iterations:
                raise GraphExecutionError(
                    f"Max iterations ({self.max_iterations}) exceeded — possible infinite loop"
                )

            updates = await self._call_node(current_node, state)
            state = self._merge(state, updates)
            iteration += 1

            self._save_checkpoint(run_id, state, current_node, iteration)

            yield current_node, dict(state)

            current_node = await self._resolve_next_async(current_node, state)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def nodes(self) -> list[str]:
        """Return registered node names."""
        return list(self._nodes.keys())

    def edges(self) -> list[tuple[str, str]]:
        """Return unconditional edges as (source, target) pairs."""
        result: list[tuple[str, str]] = []
        for src, targets in self._edges.items():
            for t in targets:
                result.append((src, t))
        return result
