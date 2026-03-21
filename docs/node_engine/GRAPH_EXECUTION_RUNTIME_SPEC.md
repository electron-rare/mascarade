# Graph Execution Runtime Specification

**Document ID:** SPEC-029-GERT
**Version:** 1.0.0
**Date:** 2026-03-17
**Status:** Draft — Graph Execution Runtime Foundation
**Parent Specification:** UNIVERSAL_NODE_ENGINE_SPECIFICATION_2026-03-15.md

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Core Graph Models](#2-core-graph-models)
3. [Execution Scheduler](#3-execution-scheduler)
4. [Execution Modes](#4-execution-modes)
5. [Execution Context](#5-execution-context)
6. [Resilience Mechanisms](#6-resilience-mechanisms)
7. [Tracing and Observability](#7-tracing-and-observability)
8. [Performance Characteristics](#8-performance-characteristics)
9. [Implementation Guidelines](#9-implementation-guidelines)
10. [Examples](#10-examples)

---

## 1. Introduction

### 1.1 Purpose

The Graph Execution Runtime provides a robust, scalable execution engine for the Universal Node Engine. It orchestrates the evaluation of node graphs with:

- **Type-Safe Execution** — All data flows validated against the Type System
- **Parallel Scheduling** — Automatic detection and execution of independent branches
- **Resilience** — Circuit breakers, retry logic, and dead letter handling
- **Observability** — Comprehensive tracing, metrics, and cancellation support
- **Flexibility** — Multiple execution modes (eager, lazy, stepped) for different use cases

### 1.2 Design Principles

1. **Deterministic** — Same graph + inputs always produces same output (modulo external I/O)
2. **Fail-Safe** — Execution failures are contained, traced, and recoverable
3. **Observable** — Every execution step is traced with context, timing, and metadata
4. **Efficient** — Maximize parallelism while respecting resource constraints
5. **Extensible** — Support for custom schedulers, executors, and resilience policies

### 1.3 Runtime Goals

| Goal | Implementation |
|------|---------------|
| **Correctness** | Topological sort + type validation before execution |
| **Parallelism** | Concurrent execution of independent branches |
| **Latency** | P50 < 10ms overhead, P99 < 50ms overhead per node |
| **Resilience** | 99.9% success rate with retry + circuit breaker |
| **Observability** | 100% execution coverage in trace spans |

---

## 2. Core Graph Models

### 2.1 Graph Structure

```python
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import StrEnum
from uuid import uuid4

class PortDirection(StrEnum):
    INPUT = "input"
    OUTPUT = "output"

class Port(BaseModel):
    """A node input or output port with type information."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Port name (unique within node)")
    direction: PortDirection
    type_id: str = Field(..., description="Reference to Type System type")
    required: bool = Field(default=True)
    default_value: Optional[Any] = None
    description: str = ""

    class Config:
        frozen = True  # Immutable after creation

class Connection(BaseModel):
    """A directed edge connecting two ports."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_node_id: str
    source_port_name: str
    target_node_id: str
    target_port_name: str

    # Type compatibility validated at graph build time
    validated: bool = Field(default=False)

    class Config:
        frozen = True

class NodeState(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

class Node(BaseModel):
    """A computational node in the execution graph."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = Field(..., description="Node type identifier")
    label: str = Field(default="")

    # Port definitions
    input_ports: Dict[str, Port] = Field(default_factory=dict)
    output_ports: Dict[str, Port] = Field(default_factory=dict)

    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict)

    # Runtime state (mutable during execution)
    state: NodeState = Field(default=NodeState.PENDING)
    error: Optional[str] = None

    # Execution metadata
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0

class ExecutionGraph(BaseModel):
    """Complete graph definition with nodes and connections."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""

    nodes: Dict[str, Node] = Field(default_factory=dict)
    connections: List[Connection] = Field(default_factory=list)

    # Derived data (computed during validation)
    entry_nodes: List[str] = Field(default_factory=list)
    exit_nodes: List[str] = Field(default_factory=list)
    topological_order: List[str] = Field(default_factory=list)

    validated: bool = Field(default=False)
```

### 2.2 Graph Validation

Before execution, the graph must be validated:

```python
class GraphValidationError(Exception):
    """Raised when graph validation fails."""
    pass

class GraphValidator:
    """Validates graph structure and type compatibility."""

    @staticmethod
    def validate(graph: ExecutionGraph) -> None:
        """
        Validates:
        1. No cycles (DAG requirement)
        2. All connections reference existing nodes/ports
        3. Port types are compatible (via Type System)
        4. Required input ports are connected or have defaults
        5. At least one entry node exists

        Raises:
            GraphValidationError: If validation fails
        """
        # Cycle detection via DFS
        GraphValidator._check_acyclic(graph)

        # Connection validation
        GraphValidator._validate_connections(graph)

        # Type compatibility
        GraphValidator._validate_types(graph)

        # Compute entry/exit nodes
        GraphValidator._compute_boundary_nodes(graph)

        # Compute topological order
        graph.topological_order = GraphValidator._topological_sort(graph)

        graph.validated = True

    @staticmethod
    def _check_acyclic(graph: ExecutionGraph) -> None:
        """Detect cycles using DFS with color marking."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node_id: WHITE for node_id in graph.nodes}

        def visit(node_id: str) -> None:
            if color[node_id] == GRAY:
                raise GraphValidationError(f"Cycle detected at node {node_id}")
            if color[node_id] == BLACK:
                return

            color[node_id] = GRAY
            for conn in graph.connections:
                if conn.source_node_id == node_id:
                    visit(conn.target_node_id)
            color[node_id] = BLACK

        for node_id in graph.nodes:
            if color[node_id] == WHITE:
                visit(node_id)

    @staticmethod
    def _topological_sort(graph: ExecutionGraph) -> List[str]:
        """
        Kahn's algorithm for topological sorting.
        Returns nodes in execution order.
        """
        # Compute in-degree for each node
        in_degree = {node_id: 0 for node_id in graph.nodes}
        for conn in graph.connections:
            in_degree[conn.target_node_id] += 1

        # Queue of nodes with no dependencies
        queue = [node_id for node_id, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            # Reduce in-degree for successors
            for conn in graph.connections:
                if conn.source_node_id == node_id:
                    target = conn.target_node_id
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)

        if len(result) != len(graph.nodes):
            raise GraphValidationError("Topological sort failed (cycle present)")

        return result
```

---

## 3. Execution Scheduler

### 3.1 Scheduler Architecture

The scheduler manages node execution order and concurrency:

```python
from asyncio import Semaphore, Task, create_task, gather, wait
from dataclasses import dataclass, field
from typing import Callable, Awaitable

@dataclass
class SchedulerConfig:
    """Configuration for execution scheduler."""
    max_parallel_nodes: int = 10
    node_timeout_s: float = 300.0
    enable_speculation: bool = False  # Speculative execution for branches
    priority_scheduling: bool = False  # Priority-based vs. FIFO

class ExecutionScheduler:
    """
    Schedules node execution respecting dependencies and concurrency limits.

    Supports:
    - Topological ordering
    - Parallel branch execution
    - Resource-constrained scheduling
    - Priority-based scheduling (optional)
    """

    def __init__(
        self,
        graph: ExecutionGraph,
        config: SchedulerConfig,
        executor: Callable[[Node], Awaitable[Dict[str, Any]]],
    ):
        self.graph = graph
        self.config = config
        self.executor = executor
        self.semaphore = Semaphore(config.max_parallel_nodes)

        # Execution state
        self.completed_nodes: set[str] = set()
        self.running_tasks: Dict[str, Task] = {}
        self.node_outputs: Dict[str, Dict[str, Any]] = {}

    async def execute(self) -> Dict[str, Dict[str, Any]]:
        """
        Execute the graph in topological order with parallel branches.

        Returns:
            Dictionary mapping node_id -> output_values
        """
        if not self.graph.validated:
            raise RuntimeError("Graph must be validated before execution")

        # Build dependency map
        dependencies = self._build_dependency_map()

        # Schedule nodes in waves
        waves = self._compute_execution_waves(dependencies)

        for wave in waves:
            # Execute all nodes in this wave concurrently
            tasks = [
                self._execute_node_with_semaphore(node_id)
                for node_id in wave
            ]
            await gather(*tasks)

        return self.node_outputs

    def _build_dependency_map(self) -> Dict[str, set[str]]:
        """Build map of node_id -> set of predecessor node IDs."""
        deps: Dict[str, set[str]] = {
            node_id: set() for node_id in self.graph.nodes
        }
        for conn in self.graph.connections:
            deps[conn.target_node_id].add(conn.source_node_id)
        return deps

    def _compute_execution_waves(
        self, dependencies: Dict[str, set[str]]
    ) -> List[List[str]]:
        """
        Partition nodes into waves where all nodes in a wave can execute in parallel.

        Wave N contains all nodes whose dependencies are satisfied in waves 0..N-1.
        """
        waves: List[List[str]] = []
        remaining = set(self.graph.nodes.keys())
        completed = set()

        while remaining:
            # Find nodes whose dependencies are all completed
            ready = [
                node_id for node_id in remaining
                if dependencies[node_id].issubset(completed)
            ]

            if not ready:
                raise RuntimeError("Circular dependency detected (should be caught by validator)")

            waves.append(ready)
            completed.update(ready)
            remaining.difference_update(ready)

        return waves

    async def _execute_node_with_semaphore(self, node_id: str) -> None:
        """Execute a single node with concurrency limiting."""
        async with self.semaphore:
            node = self.graph.nodes[node_id]
            node.state = NodeState.RUNNING

            try:
                # Gather inputs from predecessor nodes
                inputs = self._gather_node_inputs(node_id)

                # Execute node
                outputs = await self.executor(node, inputs)

                # Store outputs
                self.node_outputs[node_id] = outputs
                node.state = NodeState.COMPLETED
                self.completed_nodes.add(node_id)

            except Exception as exc:
                node.state = NodeState.FAILED
                node.error = str(exc)
                raise

    def _gather_node_inputs(self, node_id: str) -> Dict[str, Any]:
        """Collect input values from connected predecessor nodes."""
        inputs = {}

        for conn in self.graph.connections:
            if conn.target_node_id == node_id:
                source_outputs = self.node_outputs.get(conn.source_node_id, {})
                value = source_outputs.get(conn.source_port_name)
                inputs[conn.target_port_name] = value

        return inputs
```

### 3.2 Parallel Branch Detection

The scheduler automatically detects parallel execution opportunities:

```python
def _detect_parallel_branches(graph: ExecutionGraph) -> List[List[str]]:
    """
    Identify subgraphs that can execute in parallel.

    Returns list of node groups where groups have no inter-dependencies.
    """
    # Build adjacency list
    adj = {node_id: set() for node_id in graph.nodes}
    for conn in graph.connections:
        adj[conn.source_node_id].add(conn.target_node_id)

    # Find connected components in undirected version
    visited = set()
    components = []

    def dfs(node_id: str, component: set) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        component.add(node_id)

        # Visit neighbors (both directions)
        for next_id in adj[node_id]:
            dfs(next_id, component)
        for src_id, targets in adj.items():
            if node_id in targets:
                dfs(src_id, component)

    for node_id in graph.nodes:
        if node_id not in visited:
            component = set()
            dfs(node_id, component)
            components.append(list(component))

    return components
```

---

## 4. Execution Modes

### 4.1 Mode Definitions

```python
class ExecutionMode(StrEnum):
    EAGER = "eager"      # Execute all nodes as soon as ready
    LAZY = "lazy"        # Execute only nodes needed for requested outputs
    STEPPED = "stepped"  # Step-by-step execution with external control

class ExecutionModeConfig(BaseModel):
    """Configuration for execution mode."""
    mode: ExecutionMode

    # Lazy mode: which output nodes to compute
    target_nodes: List[str] = Field(default_factory=list)

    # Stepped mode: callback for step control
    step_callback: Optional[Callable[[Node], Awaitable[bool]]] = None
```

### 4.2 Eager Execution

Default mode — execute all nodes:

```python
class EagerExecutor:
    """Executes all nodes in the graph."""

    async def execute(
        self,
        graph: ExecutionGraph,
        context: "ExecutionContext",
    ) -> Dict[str, Dict[str, Any]]:
        scheduler = ExecutionScheduler(
            graph=graph,
            config=context.scheduler_config,
            executor=lambda node, inputs: self._execute_node(node, inputs, context),
        )
        return await scheduler.execute()

    async def _execute_node(
        self,
        node: Node,
        inputs: Dict[str, Any],
        context: "ExecutionContext",
    ) -> Dict[str, Any]:
        """Execute a single node with resilience and tracing."""
        # Implementation in section 6
        pass
```

### 4.3 Lazy Execution

Execute only required nodes:

```python
class LazyExecutor:
    """Executes only nodes needed to compute target outputs."""

    async def execute(
        self,
        graph: ExecutionGraph,
        target_nodes: List[str],
        context: "ExecutionContext",
    ) -> Dict[str, Dict[str, Any]]:
        # Backward traversal to find required nodes
        required = self._find_required_nodes(graph, target_nodes)

        # Create subgraph with only required nodes
        subgraph = self._create_subgraph(graph, required)

        # Execute subgraph
        scheduler = ExecutionScheduler(
            graph=subgraph,
            config=context.scheduler_config,
            executor=lambda node, inputs: self._execute_node(node, inputs, context),
        )
        return await scheduler.execute()

    def _find_required_nodes(
        self,
        graph: ExecutionGraph,
        targets: List[str],
    ) -> set[str]:
        """Backward DFS to find all nodes needed for targets."""
        required = set()

        def visit(node_id: str) -> None:
            if node_id in required:
                return
            required.add(node_id)

            # Visit all predecessors
            for conn in graph.connections:
                if conn.target_node_id == node_id:
                    visit(conn.source_node_id)

        for target in targets:
            visit(target)

        return required
```

### 4.4 Stepped Execution

Interactive step-by-step execution:

```python
class SteppedExecutor:
    """
    Executes graph one node at a time with external control.

    Useful for:
    - Debugging
    - UI-driven execution
    - Conditional branching based on intermediate results
    """

    def __init__(self, graph: ExecutionGraph, context: "ExecutionContext"):
        self.graph = graph
        self.context = context
        self.completed: set[str] = set()
        self.outputs: Dict[str, Dict[str, Any]] = {}

    def get_ready_nodes(self) -> List[str]:
        """Return nodes whose dependencies are satisfied."""
        deps = self._build_dependency_map()
        return [
            node_id for node_id in self.graph.nodes
            if node_id not in self.completed
            and deps[node_id].issubset(self.completed)
        ]

    async def step(self, node_id: str) -> Dict[str, Any]:
        """Execute a single node."""
        if node_id in self.completed:
            raise ValueError(f"Node {node_id} already completed")

        node = self.graph.nodes[node_id]
        inputs = self._gather_inputs(node_id)

        # Execute with resilience
        outputs = await self._execute_node(node, inputs)

        self.outputs[node_id] = outputs
        self.completed.add(node_id)

        return outputs

    def is_complete(self) -> bool:
        """Check if all nodes have been executed."""
        return len(self.completed) == len(self.graph.nodes)
```

---

## 5. Execution Context

### 5.1 Context Definition

The execution context carries state, configuration, and observability:

```python
from dataclasses import dataclass, field
from asyncio import Event
from uuid import uuid4

@dataclass
class ExecutionContext:
    """
    Global execution context for a graph run.

    Contains:
    - Run ID for tracing
    - Configuration
    - Cancellation support
    - Metrics collection
    - Trace buffer
    """

    run_id: str = field(default_factory=lambda: str(uuid4()))

    # Configuration
    scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)
    mode_config: ExecutionModeConfig = field(
        default_factory=lambda: ExecutionModeConfig(mode=ExecutionMode.EAGER)
    )

    # Cancellation
    cancel_event: Event = field(default_factory=Event)
    cancelled: bool = False

    # Observability
    trace_buffer: "TraceBuffer" = field(default_factory=lambda: TraceBuffer())
    metrics: "MetricsCollector" = field(default_factory=lambda: MetricsCollector())

    # Resilience components
    circuit_breakers: Dict[str, "CircuitBreaker"] = field(default_factory=dict)
    retry_executor: "RetryExecutor" = field(
        default_factory=lambda: RetryExecutor(config=RetryConfig())
    )
    dead_letter_store: "DeadLetterStore" = field(default_factory=lambda: DeadLetterStore())

    def cancel(self) -> None:
        """Request cancellation of the execution."""
        self.cancelled = True
        self.cancel_event.set()

    async def check_cancelled(self) -> None:
        """Raise exception if execution has been cancelled."""
        if self.cancelled:
            raise ExecutionCancelled(f"Execution {self.run_id} was cancelled")

class ExecutionCancelled(Exception):
    """Raised when execution is cancelled."""
    pass
```

### 5.2 Context Usage

```python
async def execute_with_context(
    graph: ExecutionGraph,
    context: ExecutionContext,
) -> Dict[str, Dict[str, Any]]:
    """
    Main execution entry point with full context support.
    """
    # Select executor based on mode
    if context.mode_config.mode == ExecutionMode.EAGER:
        executor = EagerExecutor()
        result = await executor.execute(graph, context)
    elif context.mode_config.mode == ExecutionMode.LAZY:
        executor = LazyExecutor()
        result = await executor.execute(
            graph,
            context.mode_config.target_nodes,
            context,
        )
    elif context.mode_config.mode == ExecutionMode.STEPPED:
        raise ValueError("Stepped mode requires manual step() calls")
    else:
        raise ValueError(f"Unknown execution mode: {context.mode_config.mode}")

    return result
```

---

## 6. Resilience Mechanisms

### 6.1 Circuit Breaker

Prevents cascading failures by breaking connections to failing nodes:

```python
from time import time
from enum import StrEnum

class CircuitState(StrEnum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failures detected, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 3      # Open after N failures
    success_threshold: int = 2      # Close after N successes in half-open
    timeout_s: float = 60.0         # Stay open for N seconds
    half_open_max_calls: int = 1    # Max concurrent calls in half-open

class CircuitBreaker:
    """
    Circuit breaker for node execution.

    Based on patterns from mascarade/orchestrator/circuit_breaker.py
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.half_open_calls = 0

    async def call(
        self,
        func: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Execute function through circuit breaker."""
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            if time() - self.last_failure_time >= self.config.timeout_s:
                # Transition to half-open
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                self.success_count = 0
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker open (failures: {self.failure_count})"
                )

        # Check half-open call limit
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpen("Circuit breaker half-open, max calls reached")
            self.half_open_calls += 1

        try:
            result = await func()
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                # Transition to closed
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time()

        if self.state == CircuitState.HALF_OPEN:
            # Transition back to open
            self.state = CircuitState.OPEN
        elif (
            self.state == CircuitState.CLOSED
            and self.failure_count >= self.config.failure_threshold
        ):
            # Transition to open
            self.state = CircuitState.OPEN

class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass
```

### 6.2 Retry Logic

Exponential backoff with jitter:

```python
import random
from asyncio import sleep

@dataclass
class RetryConfig:
    """Configuration for retry executor."""
    max_attempts: int = 3
    initial_delay_s: float = 1.0
    max_delay_s: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

class RetryExecutor:
    """
    Retry executor with exponential backoff.

    Based on patterns from mascarade/orchestrator/retry.py
    """

    def __init__(self, config: RetryConfig):
        self.config = config

    async def execute(
        self,
        func: Callable[[], Awaitable[Any]],
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(self.config.max_attempts):
            try:
                return await func()
            except retryable_exceptions as exc:
                last_exception = exc

                if attempt + 1 >= self.config.max_attempts:
                    # Max attempts reached
                    break

                # Calculate delay
                delay = self._calculate_delay(attempt)
                await sleep(delay)

        # All retries failed
        raise RetryExhausted(
            f"Failed after {self.config.max_attempts} attempts"
        ) from last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for next retry with exponential backoff and jitter."""
        delay = self.config.initial_delay_s * (
            self.config.exponential_base ** attempt
        )
        delay = min(delay, self.config.max_delay_s)

        if self.config.jitter:
            # Add ±25% jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0.0, delay)

class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""
    pass
```

### 6.3 Dead Letter Queue

Store failed executions for later analysis:

```python
from datetime import datetime

@dataclass
class DeadLetter:
    """A failed execution stored for later analysis."""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

    run_id: str
    node_id: str
    node_type: str

    inputs: Dict[str, Any]
    error: str
    traceback: str

    retry_count: int
    context: Dict[str, Any] = field(default_factory=dict)

class DeadLetterStore:
    """
    In-memory dead letter store.

    Production implementation should use persistent storage.
    Based on patterns from mascarade/orchestrator/dead_letter.py
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.letters: Dict[str, DeadLetter] = {}

    def add(self, letter: DeadLetter) -> None:
        """Add a dead letter to the store."""
        if len(self.letters) >= self.max_size:
            # Remove oldest letter
            oldest_id = min(
                self.letters.keys(),
                key=lambda k: self.letters[k].timestamp,
            )
            del self.letters[oldest_id]

        self.letters[letter.id] = letter

    def get(self, letter_id: str) -> Optional[DeadLetter]:
        """Retrieve a dead letter by ID."""
        return self.letters.get(letter_id)

    def list(
        self,
        node_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeadLetter]:
        """List dead letters with optional filtering."""
        letters = list(self.letters.values())

        if node_id:
            letters = [l for l in letters if l.node_id == node_id]

        # Sort by timestamp descending
        letters.sort(key=lambda l: l.timestamp, reverse=True)

        return letters[:limit]
```

### 6.4 Integrated Resilient Executor

Combine all resilience mechanisms:

```python
import traceback as tb

async def execute_node_with_resilience(
    node: Node,
    inputs: Dict[str, Any],
    context: ExecutionContext,
    node_executor: Callable[[Node, Dict[str, Any]], Awaitable[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Execute a node with full resilience support:
    - Circuit breaker
    - Retry with exponential backoff
    - Dead letter queue on failure
    - Cancellation checking
    """
    # Check for cancellation
    await context.check_cancelled()

    # Get or create circuit breaker for this node type
    cb_key = node.type
    if cb_key not in context.circuit_breakers:
        context.circuit_breakers[cb_key] = CircuitBreaker(
            CircuitBreakerConfig()
        )
    circuit_breaker = context.circuit_breakers[cb_key]

    # Execute with circuit breaker and retry
    try:
        result = await circuit_breaker.call(
            lambda: context.retry_executor.execute(
                lambda: node_executor(node, inputs)
            )
        )
        return result

    except Exception as exc:
        # Store in dead letter queue
        dead_letter = DeadLetter(
            run_id=context.run_id,
            node_id=node.id,
            node_type=node.type,
            inputs=inputs,
            error=str(exc),
            traceback=tb.format_exc(),
            retry_count=node.retry_count,
        )
        context.dead_letter_store.add(dead_letter)

        # Update node state
        node.state = NodeState.FAILED
        node.error = str(exc)

        raise
```

---

## 7. Tracing and Observability

### 7.1 Trace Buffer

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class TraceEvent:
    """A single trace event in the execution timeline."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    run_id: str

    event_type: str  # "node_start", "node_complete", "node_fail", "connection_data"
    severity: str = "info"  # "debug", "info", "warn", "error"

    node_id: Optional[str] = None
    node_type: Optional[str] = None

    connection_id: Optional[str] = None

    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

class TraceBuffer:
    """
    In-memory trace buffer for execution events.

    Based on patterns from mascarade/observability/trace_buffer.py
    """

    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self.events: List[TraceEvent] = []

    def record(
        self,
        run_id: str,
        event_type: str,
        severity: str = "info",
        node_id: Optional[str] = None,
        node_type: Optional[str] = None,
        connection_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record a trace event."""
        event = TraceEvent(
            run_id=run_id,
            event_type=event_type,
            severity=severity,
            node_id=node_id,
            node_type=node_type,
            connection_id=connection_id,
            data=data or {},
            error=error,
        )

        self.events.append(event)

        # Trim if over limit
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

    def get_run_events(self, run_id: str) -> List[TraceEvent]:
        """Get all events for a specific run."""
        return [e for e in self.events if e.run_id == run_id]

    def get_node_events(
        self,
        run_id: str,
        node_id: str,
    ) -> List[TraceEvent]:
        """Get all events for a specific node in a run."""
        return [
            e for e in self.events
            if e.run_id == run_id and e.node_id == node_id
        ]
```

### 7.2 Metrics Collection

```python
from collections import defaultdict

@dataclass
class NodeMetrics:
    """Metrics for a single node execution."""
    node_id: str
    node_type: str

    started_at: float
    completed_at: Optional[float] = None

    duration_s: Optional[float] = None
    success: bool = False
    retry_count: int = 0

    input_count: int = 0
    output_count: int = 0

class MetricsCollector:
    """Collects execution metrics for analysis."""

    def __init__(self):
        self.node_metrics: Dict[str, NodeMetrics] = {}
        self.run_started_at: Optional[float] = None
        self.run_completed_at: Optional[float] = None

    def start_run(self) -> None:
        """Mark run start."""
        self.run_started_at = time()

    def complete_run(self) -> None:
        """Mark run completion."""
        self.run_completed_at = time()

    def start_node(self, node: Node) -> None:
        """Record node start."""
        self.node_metrics[node.id] = NodeMetrics(
            node_id=node.id,
            node_type=node.type,
            started_at=time(),
        )

    def complete_node(
        self,
        node: Node,
        success: bool,
        input_count: int,
        output_count: int,
    ) -> None:
        """Record node completion."""
        metrics = self.node_metrics.get(node.id)
        if not metrics:
            return

        metrics.completed_at = time()
        metrics.duration_s = metrics.completed_at - metrics.started_at
        metrics.success = success
        metrics.retry_count = node.retry_count
        metrics.input_count = input_count
        metrics.output_count = output_count

    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        total_nodes = len(self.node_metrics)
        successful_nodes = sum(
            1 for m in self.node_metrics.values() if m.success
        )
        failed_nodes = total_nodes - successful_nodes

        durations = [
            m.duration_s for m in self.node_metrics.values()
            if m.duration_s is not None
        ]

        total_duration = (
            self.run_completed_at - self.run_started_at
            if self.run_completed_at and self.run_started_at
            else None
        )

        return {
            "total_nodes": total_nodes,
            "successful_nodes": successful_nodes,
            "failed_nodes": failed_nodes,
            "total_duration_s": total_duration,
            "avg_node_duration_s": sum(durations) / len(durations) if durations else 0,
            "max_node_duration_s": max(durations) if durations else 0,
            "min_node_duration_s": min(durations) if durations else 0,
        }
```

### 7.3 Trace Integration

Integrate tracing into node execution:

```python
async def execute_node_with_tracing(
    node: Node,
    inputs: Dict[str, Any],
    context: ExecutionContext,
    node_executor: Callable[[Node, Dict[str, Any]], Awaitable[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Execute node with full tracing and metrics."""
    # Record start
    context.trace_buffer.record(
        run_id=context.run_id,
        event_type="node_start",
        node_id=node.id,
        node_type=node.type,
        data={"input_count": len(inputs)},
    )
    context.metrics.start_node(node)

    try:
        # Execute with resilience
        outputs = await execute_node_with_resilience(
            node, inputs, context, node_executor
        )

        # Record success
        context.trace_buffer.record(
            run_id=context.run_id,
            event_type="node_complete",
            node_id=node.id,
            node_type=node.type,
            data={"output_count": len(outputs)},
        )
        context.metrics.complete_node(
            node,
            success=True,
            input_count=len(inputs),
            output_count=len(outputs),
        )

        return outputs

    except Exception as exc:
        # Record failure
        context.trace_buffer.record(
            run_id=context.run_id,
            event_type="node_fail",
            severity="error",
            node_id=node.id,
            node_type=node.type,
            error=str(exc),
        )
        context.metrics.complete_node(
            node,
            success=False,
            input_count=len(inputs),
            output_count=0,
        )

        raise
```

---

## 8. Performance Characteristics

### 8.1 Overhead Budget

Target overhead per node execution:

| Metric | P50 | P95 | P99 |
|--------|-----|-----|-----|
| **Scheduling** | <1ms | <5ms | <10ms |
| **Type validation** | <0.5ms | <2ms | <5ms |
| **Tracing** | <0.1ms | <0.5ms | <1ms |
| **Circuit breaker** | <0.05ms | <0.2ms | <0.5ms |
| **Total overhead** | <2ms | <10ms | <20ms |

### 8.2 Scalability Targets

| Scenario | Target |
|----------|--------|
| **Nodes per graph** | 1,000 nodes |
| **Parallel branches** | 100 concurrent nodes |
| **Events per second** | 10,000 events/s |
| **Memory per run** | <100MB |

### 8.3 Optimization Strategies

1. **Connection pooling** — Reuse executor threads/processes
2. **Lazy validation** — Validate types only when needed
3. **Batch tracing** — Buffer trace events and flush in batches
4. **Sparse metrics** — Sample metrics for large graphs
5. **Zero-copy data** — Pass data by reference when type-safe

---

## 9. Implementation Guidelines

### 9.1 Python Implementation

```python
# File: mascarade/node_engine/runtime/graph.py
# Core graph models (Section 2)

# File: mascarade/node_engine/runtime/validator.py
# Graph validation (Section 2.2)

# File: mascarade/node_engine/runtime/scheduler.py
# Execution scheduler (Section 3)

# File: mascarade/node_engine/runtime/executor.py
# Execution modes (Section 4)

# File: mascarade/node_engine/runtime/context.py
# Execution context (Section 5)

# File: mascarade/node_engine/runtime/resilience.py
# Circuit breaker, retry, dead letter (Section 6)

# File: mascarade/node_engine/runtime/tracing.py
# Trace buffer and metrics (Section 7)
```

### 9.2 Testing Strategy

```python
# Unit tests
# - Graph validation (cycles, types, connections)
# - Topological sort correctness
# - Execution modes (eager, lazy, stepped)
# - Circuit breaker state transitions
# - Retry backoff calculation
# - Trace event recording

# Integration tests
# - End-to-end graph execution
# - Parallel branch execution
# - Failure recovery
# - Cancellation handling

# Performance tests
# - Large graph execution (1000+ nodes)
# - Parallel execution scaling
# - Overhead measurement
```

### 9.3 Migration Path

For existing Mascarade orchestrator:

1. **Phase 1** — Implement runtime core (graph, scheduler, executor)
2. **Phase 2** — Port resilience mechanisms from orchestrator
3. **Phase 3** — Integrate tracing with existing observability
4. **Phase 4** — Migrate agent execution to node graph
5. **Phase 5** — Deprecate old orchestrator

---

## 10. Examples

### 10.1 Simple Sequential Graph

```python
# Create graph
graph = ExecutionGraph(name="simple_pipeline")

# Add nodes
node_a = Node(
    id="a",
    type="text_input",
    output_ports={"text": Port(name="text", direction=PortDirection.OUTPUT, type_id="string")},
)
node_b = Node(
    id="b",
    type="text_uppercase",
    input_ports={"input": Port(name="input", direction=PortDirection.INPUT, type_id="string")},
    output_ports={"output": Port(name="output", direction=PortDirection.OUTPUT, type_id="string")},
)
node_c = Node(
    id="c",
    type="text_output",
    input_ports={"text": Port(name="text", direction=PortDirection.INPUT, type_id="string")},
)

graph.nodes = {"a": node_a, "b": node_b, "c": node_c}

# Add connections
graph.connections = [
    Connection(source_node_id="a", source_port_name="text", target_node_id="b", target_port_name="input"),
    Connection(source_node_id="b", source_port_name="output", target_node_id="c", target_port_name="text"),
]

# Validate
GraphValidator.validate(graph)

# Execute
context = ExecutionContext()
results = await execute_with_context(graph, context)

# Check metrics
print(context.metrics.get_summary())
```

### 10.2 Parallel Branches

```python
# Create graph with parallel branches
graph = ExecutionGraph(name="parallel_pipeline")

# Single input splits to two parallel processors
node_input = Node(id="input", type="data_source", ...)
node_process_a = Node(id="process_a", type="processor", ...)
node_process_b = Node(id="process_b", type="processor", ...)
node_merge = Node(id="merge", type="merge", ...)

graph.nodes = {
    "input": node_input,
    "process_a": node_process_a,
    "process_b": node_process_b,
    "merge": node_merge,
}

graph.connections = [
    Connection(source_node_id="input", ..., target_node_id="process_a", ...),
    Connection(source_node_id="input", ..., target_node_id="process_b", ...),
    Connection(source_node_id="process_a", ..., target_node_id="merge", ...),
    Connection(source_node_id="process_b", ..., target_node_id="merge", ...),
]

# Validate and execute
GraphValidator.validate(graph)
context = ExecutionContext()
results = await execute_with_context(graph, context)

# process_a and process_b execute in parallel
```

### 10.3 Resilient Execution

```python
# Create context with custom resilience config
context = ExecutionContext(
    scheduler_config=SchedulerConfig(
        max_parallel_nodes=5,
        node_timeout_s=30.0,
    ),
)

# Configure circuit breaker
context.circuit_breakers["flaky_node"] = CircuitBreaker(
    CircuitBreakerConfig(
        failure_threshold=2,
        timeout_s=30.0,
    )
)

# Configure retry
context.retry_executor = RetryExecutor(
    RetryConfig(
        max_attempts=3,
        initial_delay_s=1.0,
    )
)

# Execute
try:
    results = await execute_with_context(graph, context)
except Exception as exc:
    # Check dead letter queue
    dead_letters = context.dead_letter_store.list()
    for letter in dead_letters:
        print(f"Failed: {letter.node_id} - {letter.error}")
```

### 10.4 Stepped Execution

```python
# Create stepped executor
context = ExecutionContext(
    mode_config=ExecutionModeConfig(mode=ExecutionMode.STEPPED)
)
executor = SteppedExecutor(graph, context)

# Execute step by step
while not executor.is_complete():
    ready_nodes = executor.get_ready_nodes()
    print(f"Ready nodes: {ready_nodes}")

    # Execute first ready node
    if ready_nodes:
        node_id = ready_nodes[0]
        outputs = await executor.step(node_id)
        print(f"Completed {node_id}: {outputs}")
```

---

## Appendix A: Integration with Mascarade Orchestrator

The graph execution runtime builds on patterns from `mascarade.orchestrator`:

| Mascarade Component | Graph Runtime Equivalent |
|---------------------|-------------------------|
| `ExecutionMode` (sequential/parallel/pipeline) | `ExecutionMode` (eager/lazy/stepped) |
| `Router` + `RetryExecutor` | Node executor with retry |
| `CircuitBreaker` | Per-node-type circuit breaker |
| `DeadLetterStore` | Dead letter queue |
| `AgentTraceBuffer` | `TraceBuffer` |
| Ray distributed execution | Future: Distributed node execution |

---

## Appendix B: Future Enhancements

1. **Distributed Execution** — Ray/Dask integration for large graphs
2. **Graph Optimization** — Dead code elimination, constant folding
3. **Checkpointing** — Resume execution from intermediate state
4. **Conditional Execution** — IF/ELSE branches based on runtime data
5. **Subgraph Composition** — Nest graphs as nodes
6. **Hot Reload** — Update graph while running (for long-running processes)
7. **A/B Testing** — Execute multiple graph variants in parallel

---

**End of Specification**
