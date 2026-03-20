#!/usr/bin/env python3
"""Simple inference graph example.

Demonstrates a basic two-node graph:
1. Prompt template node (variable substitution)
2. LLM inference node (receives prompt from template)

This shows the fundamental pattern of connecting nodes via edges
and executing them in topological order.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add core to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.graph import Edge, Graph, Node
from mascarade.node_engine.runtime import ExecutionStatus, GraphRuntime
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router


async def main() -> None:
    """Run the simple inference example."""
    print("=" * 70)
    print("Simple Inference Graph Example")
    print("=" * 70)
    print()

    # Step 1: Create runtime and register AI worker
    print("Step 1: Setting up runtime...")
    runtime = GraphRuntime()

    router = Router()
    registry = AgentRegistry()
    ai_worker = AIWorker(router=router, registry=registry)
    runtime.register_worker(ai_worker)
    print(f"✓ Registered AI Worker (supports {len(ai_worker.capabilities()['node_types'])} node types)")
    print()

    # Step 2: Build the graph
    print("Step 2: Building graph...")
    print()
    print("Graph structure:")
    print("  template1 (ai.prompt-template)")
    print("      ↓ [prompt]")
    print("  llm1 (ai.llm-inference)")
    print()

    graph = Graph(
        nodes=[
            # Node 1: Prompt template with variable substitution
            Node(
                id="template1",
                type="ai.prompt-template",
                inputs={
                    "template": "You are a helpful assistant. The user asks: {{question}}",
                    "variables": {"question": "What is the capital of France?"},
                },
            ),
            # Node 2: LLM inference (receives prompt from template node)
            Node(
                id="llm1",
                type="ai.llm-inference",
                config={
                    "strategy": "best",
                    "temperature": 0.7,
                    "max_tokens": 200,
                },
            ),
        ],
        edges=[
            # Connect template output to LLM input
            Edge(
                from_node="template1",
                from_port="prompt",
                to_node="llm1",
                to_port="prompt",
            ),
        ],
        metadata={
            "id": "simple-inference-example",
            "name": "Simple Inference Example",
            "description": "Template → LLM Inference",
        },
    )

    print(f"✓ Created graph with {graph.node_count} nodes and {graph.edge_count} edge")
    print()

    # Step 3: Validate the graph
    print("Step 3: Validating graph...")
    errors = await runtime.validate_graph(graph)
    if errors:
        print("✗ Validation failed:")
        for error in errors:
            print(f"  - {error}")
        return
    print("✓ Graph validation passed")
    print()

    # Step 4: Execute the graph
    print("Step 4: Executing graph...")
    print()

    try:
        context = await runtime.execute(graph)

        if context.status == ExecutionStatus.COMPLETED:
            print("✓ Graph execution completed successfully")
            print()
            print("=" * 70)
            print("Execution Results")
            print("=" * 70)
            print()

            # Show template node result
            template_result = context.node_results.get("template1")
            if template_result:
                print(f"Node: template1 (ai.prompt-template)")
                print(f"  Status: {template_result.status}")
                print(f"  Execution time: {template_result.execution_time_ms:.2f}ms")
                print(f"  Output prompt: {template_result.outputs.get('prompt', 'N/A')[:100]}...")
                print()

            # Show LLM inference result
            llm_result = context.node_results.get("llm1")
            if llm_result:
                print(f"Node: llm1 (ai.llm-inference)")
                print(f"  Status: {llm_result.status}")
                print(f"  Execution time: {llm_result.execution_time_ms:.2f}ms")

                response = llm_result.outputs.get("response", {})
                print(f"  Model: {response.get('model', 'N/A')}")
                print(f"  Provider: {response.get('provider', 'N/A')}")
                print()
                print("  Response:")
                print(f"    {response.get('content', 'N/A')}")
                print()

                usage = llm_result.outputs.get("usage", {})
                if usage:
                    print(f"  Token usage:")
                    print(f"    Input: {usage.get('input_tokens', 0)}")
                    print(f"    Output: {usage.get('output_tokens', 0)}")
                    print(f"    Total: {usage.get('total_tokens', 0)}")
                print()

        else:
            print(f"✗ Graph execution failed with status: {context.status}")
            for node_id, result in context.node_results.items():
                if result.error:
                    print(f"  Node '{node_id}' error: {result.error}")

    except Exception as exc:
        print(f"✗ Execution error: {exc}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
