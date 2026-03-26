# LangGraph Integration Research — March 2026

## Context

Mascarade already has a Python-based Orchestrator (`core/mascarade/orchestrator/`) that dispatches
tasks to agents via the `AgentRegistry` and routes LLM calls through the `Router` with 23+
providers. This document evaluates how LangGraph could be embedded **inside** the existing
orchestration layer rather than replacing it.

## What LangGraph Brings

LangGraph (maintained by LangChain Inc.) models agent workflows as **directed state graphs**.
Each node is a Python function that reads and updates a shared `TypedDict` state; edges define
transitions and conditional branches. Key primitives:

| Primitive | Purpose |
|---|---|
| `StateGraph` | Declares a graph whose nodes share a typed state dict |
| `add_node` | Registers an async/sync function as a processing step |
| `add_edge` / `add_conditional_edges` | Wires nodes together, optionally branching on state |
| `Send` API | Dynamically spawns parallel worker nodes at runtime |
| Checkpointer | Persists state across invocations (SQLite, Postgres, Redis) |
| `interrupt` / `Command` | Human-in-the-loop breakpoints |

LangGraph does **not** force you to use LangChain models. Any callable that accepts state and
returns updated state works as a node. This is the key property that makes embedding feasible.

## Integration Strategy for Mascarade

### Option A — LangGraph as a "graph executor" behind Orchestrator (recommended)

The Orchestrator's `execute_plan()` currently runs tasks sequentially or via simple fan-out.
Replace the inner execution loop with a dynamically-built `StateGraph`:

```
Orchestrator.execute_plan(plan)
  |
  v
Build a StateGraph from plan.tasks
  - Each task -> a node that calls AgentRegistry.run(agent_name, ...)
  - Dependencies -> edges
  - Conditional re-plan -> conditional edge back to planner node
  |
  v
compiled_graph.ainvoke(initial_state)
  |
  v
Return final state to Orchestrator
```

This keeps Mascarade's Router, provider selection, circuit-breaker, and caching untouched.
LangGraph only manages the DAG execution and state threading.

### Option B — LangGraph replaces the Orchestrator entirely

Rewrite the Orchestrator as a single large StateGraph. This gives more control over
human-in-the-loop and checkpointing but requires migrating all orchestrator logic into
LangGraph nodes and edges. Higher effort, higher coupling.

### Option C — LangGraph as an optional "agent type"

Register a `LangGraphAgent` in the AgentRegistry that wraps a compiled StateGraph. The
Orchestrator dispatches to it like any other agent. This is the lowest-risk option but
limits LangGraph to single-agent-scoped graphs.

## Recommended: Option A

Option A gives the best cost/benefit ratio:

- **Preserves** existing Router, providers, AgentRegistry, circuit-breaker, caching
- **Gains** conditional branching, parallel fan-out via `Send`, built-in checkpointing
- **Avoids** rewriting the Orchestrator from scratch
- **Allows** gradual adoption: simple plans run as before, complex plans opt-in to graph mode

## Implementation Sketch

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from operator import add

class PlanState(TypedDict):
    task_results: Annotated[list[dict], add]
    plan: dict
    final_output: str | None

async def agent_task_node(state: PlanState, *, task_id: str, agent_name: str):
    """Each task node delegates to the existing AgentRegistry + Router."""
    result = await agent_registry.run(
        agent_name=agent_name,
        input=state["plan"]["tasks"][task_id]["input"],
        router=router,
    )
    return {"task_results": [{"task_id": task_id, "output": result}]}

def build_plan_graph(plan) -> StateGraph:
    graph = StateGraph(PlanState)
    for task in plan.tasks:
        graph.add_node(
            task.id,
            functools.partial(agent_task_node, task_id=task.id, agent_name=task.agent),
        )
    # Wire edges from dependency graph
    for task in plan.tasks:
        for dep in task.depends_on:
            graph.add_edge(dep, task.id)
    # Entry points = tasks with no dependencies
    roots = [t.id for t in plan.tasks if not t.depends_on]
    graph.set_entry_point(roots[0])  # or use a virtual START node
    # Exit
    leaves = [t.id for t in plan.tasks if not any(t.id in other.depends_on for other in plan.tasks)]
    for leaf in leaves:
        graph.add_edge(leaf, END)
    return graph.compile()
```

## StateGraph Patterns That Apply to Mascarade

1. **Orchestrator-Worker** — The `Send` API lets a planner node dynamically spawn N worker
   nodes. Maps directly to Mascarade's plan-and-execute pattern where the planner generates
   tasks and workers execute them.

2. **Conditional re-planning** — `add_conditional_edges` after a synthesis node can route
   back to the planner if quality checks fail, implementing the existing "re-plan on failure"
   logic more cleanly.

3. **Parallel fan-out** — Multiple independent tasks run concurrently via `Send` or by
   having multiple root nodes. LangGraph handles the join automatically.

4. **Human-in-the-loop** — The `interrupt()` primitive pauses graph execution and persists
   state. Useful for the cockpit's approval workflows.

5. **Checkpointing** — Built-in persistence means long-running orchestrations survive
   restarts. Currently Mascarade has no native checkpoint mechanism.

## Custom LLM Provider Compatibility

LangGraph nodes are plain Python functions. They do not require LangChain's `ChatModel`
interface. A node can call Mascarade's Router directly:

```python
async def llm_node(state):
    response = await router.route(
        messages=state["messages"],
        strategy="best",
        budget=state.get("budget"),
    )
    return {"messages": state["messages"] + [response]}
```

This means all 23+ Mascarade providers (OpenAI, Anthropic, Mistral, Groq, local Ollama, etc.)
work through LangGraph without writing LangChain adapter code.

## Effort Estimate

| Phase | Scope | Effort |
|---|---|---|
| 1. Proof of concept | Build `build_plan_graph()`, run one plan through it | 2-3 days |
| 2. Parallel fan-out | Wire `Send` for independent tasks, benchmark vs current | 1-2 days |
| 3. Conditional edges | Re-plan on failure, quality gates | 2 days |
| 4. Checkpointing | Add SQLite/Redis checkpointer, test restart recovery | 1-2 days |
| 5. Cockpit integration | Surface graph state in the web UI, human-in-the-loop | 3-5 days |
| **Total** | | **9-14 days** |

## Dependencies

- `langgraph >= 0.4` (pip install langgraph)
- Optional: `langgraph-checkpoint-sqlite` or `langgraph-checkpoint-postgres`
- No LangChain dependency required if using custom provider nodes

## Risks

- **Abstraction leak**: LangGraph's state reducer model (using `Annotated` types) may clash
  with Mascarade's Pydantic models. Mitigation: convert at graph boundaries.
- **Debugging complexity**: Graph execution traces are harder to read than linear logs.
  Mitigation: use LangGraph's built-in streaming and Langfuse integration (already deployed).
- **Version churn**: LangGraph API has changed significantly between 0.1 and 0.4.
  Mitigation: pin version, wrap in an adapter layer.

## Sources

- [LangGraph official site](https://www.langchain.com/langgraph)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [LangGraph overview docs](https://docs.langchain.com/oss/python/langgraph/overview)
- [Workflows and agents docs](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph: Build Stateful AI Agents in Python (Real Python)](https://realpython.com/langgraph-python/)
- [Orchestrator-Worker workflows with LangGraph](https://medium.com/@email2argha/%EF%B8%8Fdelegate-parallelize-synthesize-building-orchestrator-worker-workflows-with-langgraph-d01b767655c4)
- [LangGraph Multi-Agent Orchestration Guide 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025)
- [LangGraph Agents in Production 2026](https://use-apify.com/blog/langgraph-agents-production)
- [LangChain AI Orchestration in 2026](https://teqnovos.com/blog/why-langchain-still-leads-ai-orchestration-key-advantages-explained/)
- [Langfuse observability for LangGraph](https://langfuse.com/guides/cookbook/integration_langgraph)
