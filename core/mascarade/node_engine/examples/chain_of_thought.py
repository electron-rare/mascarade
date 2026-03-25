#!/usr/bin/env python3
"""Chain-of-thought reasoning example.

Demonstrates multi-step reasoning using the ai.chain-of-thought node.
The node performs iterative reasoning where each step builds on the previous
steps' outputs, ultimately synthesizing a final answer.

This pattern is useful for complex reasoning tasks that benefit from
step-by-step decomposition.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add core to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.graph import Graph, Node
from mascarade.node_engine.runtime import ExecutionStatus, GraphRuntime
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router


async def main() -> None:
    """Run the chain-of-thought example."""
    print("=" * 70)
    print("Chain-of-Thought Reasoning Example")
    print("=" * 70)
    print()

    # Step 1: Create runtime and register AI worker
    print("Step 1: Setting up runtime...")
    runtime = GraphRuntime()

    router = Router()
    registry = AgentRegistry()
    ai_worker = AIWorker(router=router, registry=registry)
    runtime.register_worker(ai_worker)
    print("✓ Registered AI Worker")
    print()

    # Step 2: Build the graph
    print("Step 2: Building graph...")
    print()
    print("Graph structure:")
    print("  cot1 (ai.chain-of-thought)")
    print("    Performs multi-step reasoning:")
    print("    Step 1 → Step 2 → Step 3 → Final synthesis")
    print()

    # Define a complex question that benefits from step-by-step reasoning
    question = """
    A farmer has 17 sheep. All but 9 die. How many sheep are left alive?
    Think through this step by step, considering what "all but 9" means.
    """

    graph = Graph(
        nodes=[
            # Chain-of-thought node with 3 reasoning steps
            Node(
                id="cot1",
                type="ai.chain-of-thought",
                inputs={
                    "question": question.strip(),
                    "steps": 3,
                },
                config={
                    "strategy": "best",
                    "temperature": 0.7,
                    "max_tokens": 300,
                },
            ),
        ],
        metadata={
            "id": "chain-of-thought-example",
            "name": "Chain-of-Thought Reasoning Example",
            "description": "Multi-step reasoning with ai.chain-of-thought",
        },
    )

    print(f"✓ Created graph with {graph.node_count} node")
    print(f"  Question: {question.strip()}")
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
    print("Step 4: Executing graph (this may take a few moments)...")
    print()

    try:
        context = await runtime.execute(graph)

        if context.status == ExecutionStatus.COMPLETED:
            print("✓ Graph execution completed successfully")
            print()
            print("=" * 70)
            print("Reasoning Process")
            print("=" * 70)
            print()

            # Show chain-of-thought result
            cot_result = context.node_results.get("cot1")
            if cot_result:
                print("Node: cot1 (ai.chain-of-thought)")
                print(f"  Status: {cot_result.status}")
                print(f"  Execution time: {cot_result.execution_time_ms:.2f}ms")
                print()

                # Display each reasoning step
                reasoning_steps = cot_result.outputs.get("reasoning", [])
                for i, step in enumerate(reasoning_steps, 1):
                    print(f"  Step {i}:")
                    print(f"    {step}")
                    print()

                # Display final answer
                answer = cot_result.outputs.get("answer", "N/A")
                print("  Final Answer:")
                print(f"    {answer}")
                print()

                # Display token usage
                usage = cot_result.outputs.get("usage", {})
                if usage:
                    print("  Total Token Usage (all steps):")
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
