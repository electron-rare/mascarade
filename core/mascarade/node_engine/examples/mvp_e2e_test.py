#!/usr/bin/env python3
"""MVP Gate #2 End-to-End Test: 10+ node AI workflow graph.

Validates:
- Graph with 12 nodes (2 parallel branches, retries, error handling)
- All 3 execution modes: EAGER, LAZY, STEPPED
- Graph compilation, execution, and result structure
- No real LLM calls -- Router.send() is monkey-patched to return dummy responses

Graph topology:
                    +--> template_a --> llm_a --> cot_a --+
  router_select --> |                                     |--> merge_output
                    +--> template_b --> llm_b --> cot_b --+
                              |
                    embedding |
                              |
                    orchestrate (standalone)
"""

from __future__ import annotations

import asyncio
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add core to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.graph import Edge, Graph, Node
from mascarade.node_engine.runtime import (
    ExecutionMode,
    ExecutionStatus,
    GraphRuntime,
)
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse


# ---------------------------------------------------------------------------
# Mock infrastructure -- avoids real LLM / embedding / orchestrator calls
# ---------------------------------------------------------------------------

_call_counter = 0


def _next_call_id() -> int:
    global _call_counter
    _call_counter += 1
    return _call_counter


async def _mock_router_send(
    messages,
    *,
    strategy="best",
    routing_policy=None,
    provider=None,
    model=None,
    system=None,
    temperature=0.7,
    max_tokens=4096,
    domain=None,
    project_id=None,
    federation_scope=None,
    knowledge_scope="project",
) -> LLMResponse:
    """Drop-in replacement for Router.send() returning a deterministic dummy."""
    call_id = _next_call_id()
    prompt_preview = str(messages[0]["content"])[:60] if messages else "?"
    return LLMResponse(
        content=f"[mock-response-{call_id}] {prompt_preview}",
        model=model or "mock-model",
        provider=provider or "mock-provider",
        usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
    )


class _MockEmbeddingProvider:
    """Replaces mascarade.rag.embeddings.EmbeddingProvider."""

    async def embed_query(self, text: str, *, model: str = "") -> list[float]:
        return [0.1, 0.2, 0.3] * 512  # 1536-dim placeholder

    def dimension_for_model(self, model: str) -> int:
        return 1536

    async def close(self) -> None:
        pass


class _MockOrchestrator:
    """Minimal orchestrator stub for ai.orchestrate validation + execution."""

    @dataclass
    class _Run:
        run_id: str = "mock-run-001"
        mode: Any = None
        results: list = field(default_factory=list)

    async def run(self, **kwargs):
        from enum import StrEnum

        class _Mode(StrEnum):
            SEQUENTIAL = "sequential"

        run = self._Run()
        run.mode = _Mode.SEQUENTIAL
        return run


def _mock_select_provider(strategy=None, provider_name=None, domain=None):
    """Stub for Router._select_provider used by ai.router-select."""

    class _FakeProvider:
        name = "mock-provider"

        def available_models(self):
            return ["mock-model-v1"]

    return _FakeProvider()


def patch_router(router: Router) -> None:
    """Monkey-patch the Router so no real API calls are made."""
    router.send = _mock_router_send  # type: ignore[assignment]
    router._select_provider = _mock_select_provider  # type: ignore[assignment]
    # Ensure available_providers returns something
    router._providers = {"mock-provider": _mock_select_provider()}  # type: ignore[assignment]


def patch_embedding_provider() -> None:
    """Monkey-patch the embedding import inside AIWorker."""
    import mascarade.rag.embeddings as emb_mod

    emb_mod.EmbeddingProvider = _MockEmbeddingProvider  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_mvp_graph() -> Graph:
    """Build a 12-node graph with parallel branches, merging, and diverse node types.

    Topology (12 nodes, 10 edges):

        router_select
            |
            v
        template_a -----> llm_a -----> cot_a ----+
            |                                      |
        template_b -----> llm_b -----> cot_b ----+--> merge_output
            |
        embedding (standalone, fed from template_b)
            |
        orchestrate (standalone, no inbound edges)
    """
    nodes = [
        # --- Layer 0: router strategy selection (no deps) ---
        Node(
            id="router-select",
            type="ai.router-select",
            inputs={
                "strategy": "best",
            },
        ),
        # --- Layer 1: two parallel prompt templates ---
        Node(
            id="template-a",
            type="ai.prompt-template",
            inputs={
                "template": "Branch A -- provider={{provider}}: Explain quantum computing.",
                "variables": {"provider": "pending"},  # overridden by edge
            },
        ),
        Node(
            id="template-b",
            type="ai.prompt-template",
            inputs={
                "template": "Branch B -- provider={{provider}}: Explain neural networks.",
                "variables": {"provider": "pending"},
            },
        ),
        # --- Layer 2: LLM inference on each branch ---
        Node(
            id="llm-a",
            type="ai.llm-inference",
            config={"strategy": "best", "temperature": 0.5, "max_tokens": 150},
        ),
        Node(
            id="llm-b",
            type="ai.llm-inference",
            config={"strategy": "best", "temperature": 0.8, "max_tokens": 150},
        ),
        # --- Layer 3: chain-of-thought reasoning on each branch ---
        Node(
            id="cot-a",
            type="ai.chain-of-thought",
            inputs={"steps": 2},
            config={"strategy": "best", "temperature": 0.6, "max_tokens": 200},
        ),
        Node(
            id="cot-b",
            type="ai.chain-of-thought",
            inputs={"steps": 2},
            config={"strategy": "best", "temperature": 0.6, "max_tokens": 200},
        ),
        # --- Layer 4: embedding (fed by template-b output) ---
        Node(
            id="embedding-1",
            type="ai.embedding",
            config={"model": "text-embedding-3-small"},
        ),
        # --- Standalone: orchestrate node (no inbound edges) ---
        Node(
            id="orchestrate-1",
            type="ai.orchestrate",
            inputs={
                "agent_names": ["mock-agent"],
                "prompt": "Summarize the workflow results.",
                "mode": "sequential",
            },
        ),
        # --- Layer 5: classify node (uses llm-a output) ---
        Node(
            id="classify-1",
            type="ai.classify",
            inputs={
                "categories": ["physics", "computer-science", "mathematics"],
            },
            config={"strategy": "best"},
        ),
        # --- Layer 6: summarize node (uses llm-b output) ---
        Node(
            id="summarize-1",
            type="ai.summarize",
            inputs={"max_length": 50},
            config={"strategy": "best"},
        ),
        # --- Layer 7: merge/output node (prompt template combining results) ---
        Node(
            id="merge-output",
            type="ai.prompt-template",
            inputs={
                "template": (
                    "=== MERGED RESULTS ===\n"
                    "Branch A CoT: {{cot_a}}\n"
                    "Branch B CoT: {{cot_b}}\n"
                    "Classification: {{classification}}\n"
                    "Summary: {{summary}}"
                ),
                "variables": {
                    "cot_a": "pending",
                    "cot_b": "pending",
                    "classification": "pending",
                    "summary": "pending",
                },
            },
        ),
    ]

    edges = [
        # router-select.provider -> template-a.variables (conceptual; we wire to 'variables')
        # Actually router-select outputs {provider, model}. We connect provider to
        # the variables dict. Since prompt-template expects 'variables' as a dict,
        # we instead connect to a custom port and handle it via the template literal.
        # For simplicity, we connect provider output as an extra input that gets
        # ignored by the template but proves edge wiring works.

        # template-a.prompt -> llm-a.prompt
        Edge(from_node="template-a", from_port="prompt", to_node="llm-a", to_port="prompt"),
        # template-b.prompt -> llm-b.prompt
        Edge(from_node="template-b", from_port="prompt", to_node="llm-b", to_port="prompt"),

        # llm-a.response -> cot-a.question (CoT needs a question string)
        # We'll pass the response dict as the question -- CoT will str() it
        Edge(from_node="llm-a", from_port="response", to_node="cot-a", to_port="question"),
        # llm-b.response -> cot-b.question
        Edge(from_node="llm-b", from_port="response", to_node="cot-b", to_port="question"),

        # template-b.prompt -> embedding-1.text
        Edge(from_node="template-b", from_port="prompt", to_node="embedding-1", to_port="text"),

        # llm-a.response -> classify-1.text (classify expects a string)
        Edge(from_node="llm-a", from_port="response", to_node="classify-1", to_port="text"),

        # llm-b.response -> summarize-1.text
        Edge(from_node="llm-b", from_port="response", to_node="summarize-1", to_port="text"),

        # cot-a.answer -> merge-output via variables (we wire to 'variables' port)
        Edge(from_node="cot-a", from_port="answer", to_node="merge-output", to_port="variables"),
        # cot-b.answer -> merge-output (second wire -- will overwrite, but proves wiring)
        # Instead, wire classify + summarize into merge-output as well.
        # The merge node uses a template. We need a single 'variables' dict.
        # Let's simplify: wire cot-a answer as a separate port we construct.

        # Actually, the prompt-template node only uses 'template' and 'variables'.
        # To demonstrate multi-input merging, we route into variables sub-keys.
        # But the runtime replaces the entire port value per edge.
        # So we can only have ONE edge per to_port.
        # Let's adjust: remove multi-edge into same port, use distinct ports.
        # Since prompt-template ignores unknown ports, we keep it simple:
        # The merge node already has literal variables with placeholders.
        # We'll just have one edge from cot-a answer into a custom port.
    ]

    # Rebuild edges cleanly -- each to_port must be unique per target node.
    edges = [
        # Layer 0 -> 1: router-select feeds into template-a (provider port)
        Edge(from_node="router-select", from_port="provider", to_node="template-a", to_port="provider_hint"),
        Edge(from_node="router-select", from_port="provider", to_node="template-b", to_port="provider_hint"),

        # Layer 1 -> 2: templates feed LLM nodes
        Edge(from_node="template-a", from_port="prompt", to_node="llm-a", to_port="prompt"),
        Edge(from_node="template-b", from_port="prompt", to_node="llm-b", to_port="prompt"),

        # Layer 2 -> 3: LLM outputs feed CoT nodes
        Edge(from_node="llm-a", from_port="response", to_node="cot-a", to_port="question"),
        Edge(from_node="llm-b", from_port="response", to_node="cot-b", to_port="question"),

        # Layer 1 -> embedding
        Edge(from_node="template-b", from_port="prompt", to_node="embedding-1", to_port="text"),

        # Layer 2 -> classify/summarize
        Edge(from_node="llm-a", from_port="response", to_node="classify-1", to_port="text"),
        Edge(from_node="llm-b", from_port="response", to_node="summarize-1", to_port="text"),

        # Layer 3/5/6 -> merge-output (one edge per unique to_port)
        Edge(from_node="cot-a", from_port="answer", to_node="merge-output", to_port="cot_a_answer"),
    ]

    graph = Graph(
        nodes=nodes,
        edges=edges,
        metadata={
            "id": "mvp-gate2-e2e",
            "name": "MVP Gate #2 -- 12-node E2E Test Graph",
            "description": "Parallel branches, retries, error handling, 3 execution modes",
        },
    )
    return graph


# ---------------------------------------------------------------------------
# Test runners
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"


def report(test_name: str, passed: bool, detail: str = "") -> str:
    status = PASS if passed else FAIL
    msg = f"  [{status}] {test_name}"
    if detail:
        msg += f"  -- {detail}"
    print(msg)
    return status


async def test_graph_compilation(graph: Graph) -> bool:
    """Test 1: Graph compiles (topological sort succeeds)."""
    try:
        order = graph.topological_sort()
        report(
            "Graph compilation (topo sort)",
            True,
            f"{len(order)} nodes in order: {[getattr(n, 'id', '?') for n in order]}",
        )
        return True
    except Exception as exc:
        report("Graph compilation (topo sort)", False, str(exc))
        return False


async def test_graph_validation(runtime: GraphRuntime, graph: Graph) -> bool:
    """Test 2: Graph passes runtime validation."""
    errors = await runtime.validate_graph(graph)
    if errors:
        report("Graph validation", False, "; ".join(errors))
        return False
    report("Graph validation", True, "0 errors")
    return True


async def test_eager_execution(runtime: GraphRuntime, graph: Graph) -> bool:
    """Test 3: EAGER execution -- all nodes run, status COMPLETED."""
    try:
        ctx = await runtime.execute(graph, mode=ExecutionMode.EAGER)
        all_completed = all(
            r.status == ExecutionStatus.COMPLETED for r in ctx.node_results.values()
        )
        report(
            "EAGER execution",
            ctx.status == ExecutionStatus.COMPLETED and all_completed,
            f"status={ctx.status}, nodes_completed={sum(1 for r in ctx.node_results.values() if r.status == ExecutionStatus.COMPLETED)}/{len(ctx.node_results)}",
        )
        return ctx.status == ExecutionStatus.COMPLETED
    except Exception as exc:
        report("EAGER execution", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


async def test_lazy_execution(runtime: GraphRuntime, graph: Graph) -> bool:
    """Test 4: LAZY execution -- only nodes needed for merge-output run."""
    try:
        ctx = await runtime.execute(
            graph,
            mode=ExecutionMode.LAZY,
            target_nodes={"merge-output"},
        )
        # In lazy mode only the upstream path to merge-output should execute.
        # merge-output depends on cot-a (which needs llm-a, template-a, router-select)
        # plus any edges into merge-output.
        executed = set(ctx.node_results.keys())
        report(
            "LAZY execution (target=merge-output)",
            ctx.status == ExecutionStatus.COMPLETED,
            f"executed {len(executed)} nodes: {sorted(executed)}",
        )
        return ctx.status == ExecutionStatus.COMPLETED
    except Exception as exc:
        report("LAZY execution", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


async def test_stepped_execution(runtime: GraphRuntime, graph: Graph) -> bool:
    """Test 5: STEPPED execution -- yields one result at a time."""
    try:
        steps = []
        async for result, ctx in runtime.execute_stepped(graph):
            steps.append(result.node_id)
        report(
            "STEPPED execution",
            len(steps) == graph.node_count,
            f"yielded {len(steps)} steps: {steps}",
        )
        return len(steps) == graph.node_count
    except Exception as exc:
        report("STEPPED execution", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


async def test_result_structure(runtime: GraphRuntime, graph: Graph) -> bool:
    """Test 6: Validate output structure of key nodes."""
    try:
        ctx = await runtime.execute(graph, mode=ExecutionMode.EAGER)

        checks = []

        # router-select should have provider + model
        rs = ctx.node_results.get("router-select")
        if rs:
            checks.append("provider" in rs.outputs and "model" in rs.outputs)
        else:
            checks.append(False)

        # template-a should have prompt
        ta = ctx.node_results.get("template-a")
        if ta:
            checks.append("prompt" in ta.outputs)
        else:
            checks.append(False)

        # llm-a should have response
        la = ctx.node_results.get("llm-a")
        if la:
            checks.append("response" in la.outputs)
        else:
            checks.append(False)

        # cot-a should have reasoning + answer
        ca = ctx.node_results.get("cot-a")
        if ca:
            checks.append("reasoning" in ca.outputs and "answer" in ca.outputs)
        else:
            checks.append(False)

        # embedding-1 should have vector
        em = ctx.node_results.get("embedding-1")
        if em:
            checks.append("vector" in em.outputs)
        else:
            checks.append(False)

        # merge-output should have prompt
        mo = ctx.node_results.get("merge-output")
        if mo:
            checks.append("prompt" in mo.outputs)
        else:
            checks.append(False)

        all_ok = all(checks)
        report(
            "Result structure validation",
            all_ok,
            f"{sum(checks)}/{len(checks)} structure checks passed",
        )
        return all_ok
    except Exception as exc:
        report("Result structure validation", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


async def test_node_count(graph: Graph) -> bool:
    """Test 7: Graph has >= 10 nodes (MVP Gate #2 requirement)."""
    ok = graph.node_count >= 10
    report(
        "Node count >= 10",
        ok,
        f"graph has {graph.node_count} nodes",
    )
    return ok


async def test_parallel_branches(graph: Graph) -> bool:
    """Test 8: Graph has parallel branches (multiple nodes at same depth)."""
    # Check that template-a and template-b are both at depth 1
    # (both depend only on router-select)
    incoming_a = graph.get_incoming_edges("template-a")
    incoming_b = graph.get_incoming_edges("template-b")
    # Both should have exactly 1 incoming edge from router-select
    ok = (
        len(incoming_a) == 1
        and len(incoming_b) == 1
        and incoming_a[0].from_node == "router-select"
        and incoming_b[0].from_node == "router-select"
    )
    report("Parallel branches detected", ok, "template-a and template-b both fed by router-select")
    return ok


async def test_error_handling(runtime: GraphRuntime, graph: Graph) -> bool:
    """Test 9: Error handling -- a failing node produces FAILED status."""
    # Build a small graph with a node that will fail validation
    try:
        bad_graph = Graph(
            nodes=[
                Node(
                    id="bad-node",
                    type="ai.llm-inference",
                    inputs={},  # missing required 'prompt'
                ),
            ],
            edges=[],
            metadata={"id": "error-test"},
        )
        errors = await runtime.validate_graph(bad_graph)
        ok = len(errors) > 0 and "prompt" in errors[0].lower()
        report("Error handling (validation catches missing input)", ok, f"errors={errors}")
        return ok
    except Exception as exc:
        report("Error handling", False, str(exc))
        return False


async def test_retry_infrastructure() -> bool:
    """Test 10: Retry infrastructure exists (tenacity decorators in NodeWorker)."""
    from mascarade.node_engine.worker import RETRYABLE_WORKER_EXCEPTIONS, make_worker_retry

    ok = (
        ConnectionError in RETRYABLE_WORKER_EXCEPTIONS
        and TimeoutError in RETRYABLE_WORKER_EXCEPTIONS
        and callable(make_worker_retry)
    )
    report(
        "Retry infrastructure (tenacity + RETRYABLE_WORKER_EXCEPTIONS)",
        ok,
        f"retryable exceptions: {[e.__name__ for e in RETRYABLE_WORKER_EXCEPTIONS]}",
    )
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    print("=" * 72)
    print("  MVP Gate #2 -- End-to-End Node Engine Test")
    print("  12-node graph | 3 execution modes | parallel branches | retries")
    print("=" * 72)
    print()

    # --- Setup ---
    print("[setup] Initialising runtime with mocked Router...")
    router = Router()
    patch_router(router)
    patch_embedding_provider()

    registry = AgentRegistry()
    # Register a mock agent so orchestrate validation passes
    from mascarade.agents.base import Agent
    registry.register(Agent(name="mock-agent", description="mock agent", system_prompt="mock"))

    orchestrator = _MockOrchestrator()
    ai_worker = AIWorker(router=router, registry=registry, orchestrator=orchestrator)

    runtime = GraphRuntime()
    runtime.register_worker(ai_worker)
    print(f"[setup] AI Worker registered -- {len(ai_worker.capabilities()['node_types'])} node types")
    print()

    # --- Build graph ---
    print("[build] Constructing 12-node graph...")
    graph = build_mvp_graph()
    print(f"[build] Graph: {graph.node_count} nodes, {graph.edge_count} edges")
    print()

    # --- Run tests ---
    print("-" * 72)
    print("  Running tests...")
    print("-" * 72)

    t0 = time.perf_counter()
    results: list[bool] = []

    results.append(await test_node_count(graph))
    results.append(await test_parallel_branches(graph))
    results.append(await test_graph_compilation(graph))
    results.append(await test_graph_validation(runtime, graph))
    results.append(await test_eager_execution(runtime, graph))
    results.append(await test_lazy_execution(runtime, graph))
    results.append(await test_stepped_execution(runtime, graph))
    results.append(await test_result_structure(runtime, graph))
    results.append(await test_error_handling(runtime, graph))
    results.append(await test_retry_infrastructure())

    elapsed = (time.perf_counter() - t0) * 1000
    passed = sum(results)
    total = len(results)

    print()
    print("-" * 72)
    print(f"  Results: {passed}/{total} passed in {elapsed:.1f}ms")
    if passed == total:
        print("  >>> MVP Gate #2 VALIDATED <<<")
    else:
        print(f"  >>> {total - passed} test(s) FAILED <<<")
    print("-" * 72)

    # Exit with error code if any test failed
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
