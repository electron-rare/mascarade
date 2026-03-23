#!/usr/bin/env python3
"""Agent orchestration example.

Demonstrates multi-agent orchestration patterns using the AI Worker:
1. Sequential orchestration: Agents run one after another
2. Parallel orchestration: Agents run concurrently
3. Pipeline orchestration: Each agent's output feeds into the next

This shows how to coordinate multiple specialized agents through
the Universal Node Engine.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add core to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.node_engine.graph import Graph, Node
from mascarade.node_engine.runtime import ExecutionStatus, GraphRuntime
from mascarade.node_engine.workers.ai.worker import AIWorker
from mascarade.router import Router
from mascarade.router.router import Strategy


async def main() -> None:
    """Run the agent orchestration example."""
    print("=" * 70)
    print("Agent Orchestration Example")
    print("=" * 70)
    print()

    # Step 1: Create runtime and register agents
    print("Step 1: Setting up runtime and registering agents...")
    runtime = GraphRuntime()

    router = Router()
    registry = AgentRegistry()

    # Register example agents with different specializations
    registry.register(
        Agent(
            name="analyzer",
            description="Analyzes the problem and breaks it down",
            system_prompt="You are an expert at analyzing problems and breaking them down into components.",
            strategy=Strategy.BEST,
            temperature=0.3,
        )
    )

    registry.register(
        Agent(
            name="researcher",
            description="Researches relevant information",
            system_prompt="You are a research expert who finds relevant information and context.",
            strategy=Strategy.BEST,
            temperature=0.5,
        )
    )

    registry.register(
        Agent(
            name="synthesizer",
            description="Synthesizes information into a coherent answer",
            system_prompt="You are an expert at synthesizing information into clear, coherent answers.",
            strategy=Strategy.BEST,
            temperature=0.7,
        )
    )

    registry.register(
        Agent(
            name="critic",
            description="Critically evaluates the solution",
            system_prompt="You are a critical thinker who evaluates solutions for accuracy and completeness.",
            strategy=Strategy.BEST,
            temperature=0.4,
        )
    )

    ai_worker = AIWorker(router=router, registry=registry)
    runtime.register_worker(ai_worker)

    print("✓ Registered AI Worker")
    print(f"✓ Registered {len(registry.list())} agents:")
    for agent in registry.list():
        print(f"    - {agent.name}: {agent.description}")
    print()

    # Step 2: Run different orchestration patterns
    await run_sequential_example(runtime)
    await run_parallel_example(runtime)
    await run_pipeline_example(runtime)


async def run_sequential_example(runtime: GraphRuntime) -> None:
    """Run sequential orchestration example."""
    print("=" * 70)
    print("Example 1: Sequential Orchestration")
    print("=" * 70)
    print()
    print("Pattern: analyzer → researcher → synthesizer (one after another)")
    print()

    graph = Graph(
        nodes=[
            Node(
                id="seq1",
                type="ai.orchestrate-sequential",
                inputs={
                    "agents": ["analyzer", "researcher", "synthesizer"],
                    "initial_prompt": "Explain how photosynthesis works in simple terms.",
                },
                config={
                    "strategy": "best",
                    "temperature": 0.7,
                },
            ),
        ],
        metadata={
            "id": "sequential-orchestration",
            "name": "Sequential Orchestration Example",
        },
    )

    print("Executing graph...")
    try:
        context = await runtime.execute(graph)

        if context.status == ExecutionStatus.COMPLETED:
            print("✓ Sequential orchestration completed")
            print()

            result = context.node_results.get("seq1")
            if result:
                results_list = result.outputs.get("results", [])
                final = result.outputs.get("final", {})

                print(f"Execution time: {result.execution_time_ms:.2f}ms")
                print(f"Agents executed: {len(results_list)}")
                print()
                print("Final output:")
                print(f"  {final.get('content', 'N/A')[:200]}...")
                print()

        else:
            print(f"✗ Execution failed: {context.status}")

    except Exception as exc:
        print(f"✗ Error: {exc}")

    print()


async def run_parallel_example(runtime: GraphRuntime) -> None:
    """Run parallel orchestration example."""
    print("=" * 70)
    print("Example 2: Parallel Orchestration")
    print("=" * 70)
    print()
    print("Pattern: analyzer ∥ researcher ∥ critic (all at once)")
    print()

    graph = Graph(
        nodes=[
            Node(
                id="par1",
                type="ai.orchestrate-parallel",
                inputs={
                    "agents": ["analyzer", "researcher", "critic"],
                    "prompt": "What are the key challenges in renewable energy adoption?",
                },
                config={
                    "strategy": "best",
                    "temperature": 0.6,
                },
            ),
        ],
        metadata={
            "id": "parallel-orchestration",
            "name": "Parallel Orchestration Example",
        },
    )

    print("Executing graph...")
    try:
        context = await runtime.execute(graph)

        if context.status == ExecutionStatus.COMPLETED:
            print("✓ Parallel orchestration completed")
            print()

            result = context.node_results.get("par1")
            if result:
                results_list = result.outputs.get("results", [])

                print(f"Execution time: {result.execution_time_ms:.2f}ms")
                print(f"Agents executed: {len(results_list)}")
                print()
                print("Outputs from each agent:")
                for i, agent_result in enumerate(results_list):
                    content = agent_result.get("content", "N/A")
                    print(f"  Agent {i+1}: {content[:100]}...")
                print()

        else:
            print(f"✗ Execution failed: {context.status}")

    except Exception as exc:
        print(f"✗ Error: {exc}")

    print()


async def run_pipeline_example(runtime: GraphRuntime) -> None:
    """Run pipeline orchestration example."""
    print("=" * 70)
    print("Example 3: Pipeline Orchestration")
    print("=" * 70)
    print()
    print("Pattern: analyzer → researcher → synthesizer → critic (chained)")
    print("Each agent's output feeds into the next agent")
    print()

    graph = Graph(
        nodes=[
            Node(
                id="pipe1",
                type="ai.orchestrate-pipeline",
                inputs={
                    "agents": ["analyzer", "researcher", "synthesizer", "critic"],
                    "initial_prompt": "How can we reduce plastic waste in oceans?",
                },
                config={
                    "strategy": "best",
                    "temperature": 0.7,
                },
            ),
        ],
        metadata={
            "id": "pipeline-orchestration",
            "name": "Pipeline Orchestration Example",
        },
    )

    print("Executing graph...")
    try:
        context = await runtime.execute(graph)

        if context.status == ExecutionStatus.COMPLETED:
            print("✓ Pipeline orchestration completed")
            print()

            result = context.node_results.get("pipe1")
            if result:
                results_list = result.outputs.get("results", [])
                final = result.outputs.get("final", {})

                print(f"Execution time: {result.execution_time_ms:.2f}ms")
                print(f"Pipeline stages: {len(results_list)}")
                print()
                print("Intermediate outputs:")
                for i, stage_result in enumerate(results_list):
                    content = stage_result.get("content", "N/A")
                    print(f"  Stage {i+1}: {content[:80]}...")
                print()
                print("Final pipeline output:")
                print(f"  {final.get('content', 'N/A')[:200]}...")
                print()

        else:
            print(f"✗ Execution failed: {context.status}")

    except Exception as exc:
        print(f"✗ Error: {exc}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
