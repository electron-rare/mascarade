"""Swarms-inspired orchestration patterns for mascarade.

Four patterns:
1. MixtureOfAgents (MoA) — parallel N agents + synthesizer
2. DAG helpers — build StateGraphs from dependency dicts
3. GroupChat — conversational loop between agents with moderator
4. AgentRearrange — parse string syntax "A -> B, C -> D" into execution plan
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("mascarade.orchestrator.patterns")


# ---------------------------------------------------------------------------
# 1. Mixture of Agents (MoA)
# ---------------------------------------------------------------------------

@dataclass
class MoAResult:
    """Result from a Mixture of Agents execution."""
    agent_results: dict[str, str]  # agent_name -> response
    synthesized: str  # final merged response
    errors: dict[str, str]  # agent_name -> error message


async def mixture_of_agents(
    query: str,
    agent_names: list[str],
    synthesizer_prompt: str | None = None,
    *,
    send_fn: Callable[..., Any],
    timeout: float = 60.0,
) -> MoAResult:
    """Run N agents in parallel on the same query, then synthesize.

    Args:
        query: The input question/task.
        agent_names: List of agent names to run in parallel.
        synthesizer_prompt: System prompt for the synthesizer. If None, uses a default.
        send_fn: Async function(agent_name, message) -> str that sends to an agent.
        timeout: Max seconds per agent call.

    Returns:
        MoAResult with individual and synthesized responses.
    """
    if not synthesizer_prompt:
        synthesizer_prompt = (
            "You are a synthesis agent. You receive multiple expert responses to the same query. "
            "Merge them into a single, coherent, comprehensive answer. "
            "Resolve contradictions by favoring the most detailed and well-reasoned response. "
            "Do not mention the individual agents."
        )

    # Run all agents in parallel
    results: dict[str, str] = {}
    errors: dict[str, str] = {}

    async def _run_agent(name: str) -> None:
        try:
            result = await asyncio.wait_for(send_fn(name, query), timeout)
            results[name] = str(result)
        except asyncio.TimeoutError:
            errors[name] = f"timeout ({timeout}s)"
        except Exception as exc:
            errors[name] = str(exc)

    await asyncio.gather(*[_run_agent(name) for name in agent_names])

    if not results:
        return MoAResult(agent_results={}, synthesized="All agents failed.", errors=errors)

    # Synthesize
    synthesis_input = "\n\n".join(
        f"--- {name} ---\n{response}" for name, response in results.items()
    )
    synthesis_query = f"Query: {query}\n\nExpert responses:\n{synthesis_input}\n\nSynthesize a unified answer."

    try:
        synthesized = await asyncio.wait_for(
            send_fn("__synthesizer__", synthesis_query),
            timeout,
        )
    except Exception as exc:
        logger.warning("Synthesizer failed: %s. Returning first result.", exc)
        synthesized = next(iter(results.values()))

    return MoAResult(agent_results=results, synthesized=str(synthesized), errors=errors)


# ---------------------------------------------------------------------------
# 2. DAG helpers
# ---------------------------------------------------------------------------

def build_dag(
    dependencies: dict[str, list[str]],
) -> list[list[str]]:
    """Build execution levels from a dependency dict.

    Args:
        dependencies: {task: [depends_on_tasks]}. Tasks with empty deps run first.

    Returns:
        List of levels, each containing tasks that can run in parallel.

    Example:
        >>> build_dag({"qa": ["architect", "firmware"], "architect": ["pm"], "firmware": ["pm"], "pm": [], "doc": ["qa"]})
        [['pm'], ['architect', 'firmware'], ['qa'], ['doc']]
    """
    in_degree: dict[str, int] = {t: 0 for t in dependencies}
    for task, deps in dependencies.items():
        in_degree[task] = len(deps)
        for dep in deps:
            if dep not in in_degree:
                in_degree[dep] = 0

    levels: list[list[str]] = []
    remaining = dict(in_degree)

    while remaining:
        level = [t for t, d in remaining.items() if d == 0]
        if not level:
            raise ValueError(f"Cycle detected in DAG. Remaining: {list(remaining.keys())}")
        levels.append(sorted(level))
        for t in level:
            del remaining[t]
        for t in remaining:
            for dep in dependencies.get(t, []):
                if dep in level:
                    remaining[t] -= 1

    return levels


async def execute_dag(
    dependencies: dict[str, list[str]],
    *,
    run_fn: Callable[[str, dict[str, str]], Any],
    timeout: float = 120.0,
) -> dict[str, str]:
    """Execute tasks in DAG order, passing upstream results.

    Args:
        dependencies: {task: [depends_on_tasks]}.
        run_fn: Async function(task_name, upstream_results) -> str.
        timeout: Max seconds per task.

    Returns:
        {task_name: result} for all tasks.
    """
    levels = build_dag(dependencies)
    all_results: dict[str, str] = {}

    for level in levels:
        async def _run(task: str) -> tuple[str, str]:
            upstream = {dep: all_results[dep] for dep in dependencies.get(task, []) if dep in all_results}
            result = await asyncio.wait_for(run_fn(task, upstream), timeout)
            return task, str(result)

        level_results = await asyncio.gather(*[_run(t) for t in level])
        for task, result in level_results:
            all_results[task] = result

    return all_results


# ---------------------------------------------------------------------------
# 3. GroupChat
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    agent: str
    content: str
    round: int


@dataclass
class GroupChatResult:
    messages: list[ChatMessage]
    rounds: int
    final_summary: str


async def group_chat(
    topic: str,
    agents: list[str],
    moderator: str | None = None,
    max_rounds: int = 5,
    *,
    send_fn: Callable[..., Any],
    timeout: float = 30.0,
) -> GroupChatResult:
    """Run a conversational loop between agents.

    Each round, every agent sees the full conversation so far and adds their perspective.
    An optional moderator summarizes after all rounds.

    Args:
        topic: The discussion topic.
        agents: List of agent names participating.
        moderator: Agent to produce final summary. If None, last message is the summary.
        max_rounds: Number of conversation rounds.
        send_fn: Async function(agent_name, message) -> str.
        timeout: Max seconds per agent turn.

    Returns:
        GroupChatResult with full transcript and summary.
    """
    messages: list[ChatMessage] = []

    for round_num in range(1, max_rounds + 1):
        for agent in agents:
            # Build context from conversation history
            history = "\n".join(
                f"[{m.agent}] (round {m.round}): {m.content}" for m in messages
            )
            prompt = (
                f"Topic: {topic}\n\n"
                f"Conversation so far:\n{history}\n\n"
                f"You are {agent}. Contribute your perspective for round {round_num}. "
                f"Build on what others said, add new insights, or respectfully disagree."
                if history else
                f"Topic: {topic}\n\nYou are {agent}. Share your initial perspective."
            )

            try:
                response = await asyncio.wait_for(send_fn(agent, prompt), timeout)
                messages.append(ChatMessage(agent=agent, content=str(response), round=round_num))
            except Exception as exc:
                messages.append(ChatMessage(agent=agent, content=f"[error: {exc}]", round=round_num))

    # Moderator summary
    if moderator:
        history = "\n".join(f"[{m.agent}] (round {m.round}): {m.content}" for m in messages)
        summary_prompt = (
            f"Topic: {topic}\n\nFull discussion:\n{history}\n\n"
            f"As moderator, synthesize the key conclusions, decisions, and action items."
        )
        try:
            summary = await asyncio.wait_for(send_fn(moderator, summary_prompt), timeout)
        except Exception:
            summary = messages[-1].content if messages else "No summary available."
    else:
        summary = messages[-1].content if messages else "No messages."

    return GroupChatResult(messages=messages, rounds=max_rounds, final_summary=str(summary))


# ---------------------------------------------------------------------------
# 4. AgentRearrange — string syntax parser
# ---------------------------------------------------------------------------

def parse_agent_flow(flow_spec: str) -> dict[str, list[str]]:
    """Parse a string flow specification into a dependency dict.

    Syntax:
        "A -> B -> C"           # sequential: C depends on B, B depends on A
        "A -> B, C -> D"        # B and C depend on A, D depends on both B and C
        "A -> B; A -> C; B, C -> D"  # explicit: A feeds B and C, D waits for both

    Args:
        flow_spec: String specification.

    Returns:
        Dependency dict suitable for build_dag() / execute_dag().

    Examples:
        >>> parse_agent_flow("pm -> architect -> qa -> doc")
        {'pm': [], 'architect': ['pm'], 'qa': ['architect'], 'doc': ['qa']}

        >>> parse_agent_flow("pm -> architect, hw_schematic -> qa -> doc")
        {'pm': [], 'architect': ['pm'], 'hw_schematic': ['pm'], 'qa': ['architect', 'hw_schematic'], 'doc': ['qa']}
    """
    deps: dict[str, list[str]] = {}

    # Split on semicolons for multiple flow statements
    statements = [s.strip() for s in flow_spec.split(";") if s.strip()]

    for statement in statements:
        # Split on -> for chain steps
        steps = [s.strip() for s in statement.split("->")]

        prev_agents: list[str] = []
        for step in steps:
            # Each step can have comma-separated agents (parallel)
            current_agents = [a.strip() for a in step.split(",") if a.strip()]

            for agent in current_agents:
                if agent not in deps:
                    deps[agent] = []
                # Add all previous step agents as dependencies
                for prev in prev_agents:
                    if prev not in deps[agent]:
                        deps[agent].append(prev)

            prev_agents = current_agents

    return deps


async def agent_rearrange(
    flow_spec: str,
    initial_input: str,
    *,
    send_fn: Callable[..., Any],
    timeout: float = 120.0,
) -> dict[str, str]:
    """Execute agents in the order defined by a flow string.

    Args:
        flow_spec: String like "pm -> architect, hw_schematic -> qa -> doc"
        initial_input: The starting input for root agents.
        send_fn: Async function(agent_name, message) -> str.
        timeout: Max seconds per agent.

    Returns:
        {agent_name: result} for all agents in the flow.
    """
    deps = parse_agent_flow(flow_spec)

    async def _run(task: str, upstream: dict[str, str]) -> str:
        if upstream:
            context = "\n\n".join(f"[{k}]:\n{v}" for k, v in upstream.items())
            message = f"Previous agent outputs:\n{context}\n\nOriginal task: {initial_input}"
        else:
            message = initial_input
        return await send_fn(task, message)

    return await execute_dag(deps, run_fn=_run, timeout=timeout)
