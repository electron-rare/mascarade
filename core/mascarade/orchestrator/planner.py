"""Plan-and-Execute orchestrator — DAG-based multi-agent task decomposition."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum

from mascarade.agents.registry import AgentRegistry
from mascarade.router import Router

logger = logging.getLogger("mascarade.orchestrator.planner")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """A single task in the execution DAG."""

    id: str
    agent: str
    input: str
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    retries: int = 0


@dataclass
class ExecutionPlan:
    """A DAG of TaskNodes produced by the planner."""

    tasks: list[TaskNode] = field(default_factory=list)
    query: str = ""

    def get_task(self, task_id: str) -> TaskNode | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def ready_tasks(self) -> list[TaskNode]:
        """Return tasks whose dependencies are all completed."""
        completed = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [
            t
            for t in self.tasks
            if t.status == TaskStatus.PENDING
            and all(dep in completed for dep in t.dependencies)
        ]

    def all_done(self) -> bool:
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED)
            for t in self.tasks
        )

    def has_failures(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    def results_summary(self) -> dict[str, str | None]:
        return {t.id: t.result for t in self.tasks}


# ---------------------------------------------------------------------------
# Planner prompt
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """\
You are a task planner. Given a user query and a list of available agents, \
decompose the query into a directed acyclic graph (DAG) of subtasks.

Each subtask must specify:
- "id": a short unique identifier (e.g. "t1", "t2")
- "agent": name of the agent to use (must be one of the available agents)
- "input": the prompt/instruction for that agent
- "dependencies": list of task ids that must complete before this task runs \
(empty list if the task can run immediately)

Rules:
- Use the fewest tasks necessary. Do not over-decompose.
- Tasks with no dependency on each other should have empty or disjoint \
dependency lists so they can run in parallel.
- The final task should synthesize/combine results if multiple tasks exist.
- Output ONLY valid JSON: a list of task objects. No commentary."""

PLANNER_USER_TEMPLATE = """\
User query: {query}

Available agents:
{agents_description}

Output the task list as JSON."""

SYNTHESIZE_SYSTEM_PROMPT = """\
You are a synthesis agent. You receive partial results from multiple agents \
and must combine them into a single coherent answer for the user."""

SYNTHESIZE_USER_TEMPLATE = """\
Original query: {query}

Results from subtasks:
{results_block}

Provide a clear, unified answer."""


# ---------------------------------------------------------------------------
# PlanAndExecuteOrchestrator
# ---------------------------------------------------------------------------


class PlanAndExecuteOrchestrator:
    """Orchestrator that plans a DAG of tasks then executes them."""

    def __init__(
        self,
        router: Router,
        registry: AgentRegistry,
        *,
        max_retries: int = 1,
        planner_model: str | None = None,
        planner_provider: str | None = None,
        timeout_per_task: float = 120.0,
    ) -> None:
        self.router = router
        self.registry = registry
        self.max_retries = max_retries
        self.planner_model = planner_model
        self.planner_provider = planner_provider
        self.timeout_per_task = timeout_per_task

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _build_agents_description(self) -> str:
        lines: list[str] = []
        for agent in self.registry.list():
            lines.append(f"- {agent.name}: {agent.description}")
        return "\n".join(lines)

    async def plan(self, query: str) -> ExecutionPlan:
        """Use the LLM router to decompose *query* into an ExecutionPlan."""
        agents_desc = self._build_agents_description()
        user_prompt = PLANNER_USER_TEMPLATE.format(
            query=query, agents_description=agents_desc
        )

        response = await self.router.send(
            [{"role": "user", "content": user_prompt}],
            system=PLANNER_SYSTEM_PROMPT,
            provider=self.planner_provider,
            model=self.planner_model,
            temperature=0.2,
            max_tokens=2048,
        )

        tasks = self._parse_plan(response.content)
        self._validate_plan(tasks)
        plan = ExecutionPlan(tasks=tasks, query=query)
        logger.info(
            "Plan created: %d tasks for query '%.80s'", len(tasks), query
        )
        return plan

    def _parse_plan(self, raw: str) -> list[TaskNode]:
        """Parse LLM output into TaskNode list."""
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (with optional language tag) and closing fence
            lines = text.split("\n")
            lines = lines[1:]  # drop opening ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Expected a JSON list of tasks")

        nodes: list[TaskNode] = []
        for item in data:
            nodes.append(
                TaskNode(
                    id=str(item["id"]),
                    agent=str(item["agent"]),
                    input=str(item["input"]),
                    dependencies=[str(d) for d in item.get("dependencies", [])],
                )
            )
        return nodes

    def _validate_plan(self, tasks: list[TaskNode]) -> None:
        """Check for basic DAG validity."""
        ids = {t.id for t in tasks}
        if len(ids) != len(tasks):
            raise ValueError("Duplicate task ids in plan")

        agent_names = {a.name for a in self.registry.list()}
        for t in tasks:
            if t.agent not in agent_names:
                raise ValueError(
                    f"Task '{t.id}' references unknown agent '{t.agent}'. "
                    f"Available: {sorted(agent_names)}"
                )
            for dep in t.dependencies:
                if dep not in ids:
                    raise ValueError(
                        f"Task '{t.id}' depends on unknown task '{dep}'"
                    )

        # Simple cycle detection via topological sort attempt
        remaining = {t.id: set(t.dependencies) for t in tasks}
        resolved: set[str] = set()
        while remaining:
            batch = {tid for tid, deps in remaining.items() if deps <= resolved}
            if not batch:
                raise ValueError("Cycle detected in task dependencies")
            resolved |= batch
            for tid in batch:
                del remaining[tid]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Execute the plan, running independent tasks in parallel."""
        while not plan.all_done():
            ready = plan.ready_tasks()
            if not ready:
                # No tasks ready but not all done means unresolvable deps
                for t in plan.tasks:
                    if t.status == TaskStatus.PENDING:
                        t.status = TaskStatus.SKIPPED
                        t.error = "Unresolvable dependency (upstream failed)"
                break

            # Run all ready tasks in parallel
            coros = [self._run_task(task, plan) for task in ready]
            await asyncio.gather(*coros)

        return plan

    async def _run_task(self, task: TaskNode, plan: ExecutionPlan) -> None:
        """Execute a single task node using the appropriate agent."""
        task.status = TaskStatus.RUNNING
        agent = self.registry.get(task.agent)

        # Inject upstream results into the task input
        enriched_input = self._enrich_input(task, plan)

        try:
            response = await asyncio.wait_for(
                agent.run(enriched_input, router=self.router),
                timeout=self.timeout_per_task,
            )
            task.result = response.content
            task.status = TaskStatus.COMPLETED
            logger.info("Task '%s' completed (agent=%s)", task.id, task.agent)
        except Exception as exc:
            logger.error("Task '%s' failed: %s", task.id, exc)
            task.error = str(exc)
            if task.retries < self.max_retries:
                task.retries += 1
                task.status = TaskStatus.PENDING
                logger.info(
                    "Task '%s' scheduled for retry (%d/%d)",
                    task.id,
                    task.retries,
                    self.max_retries,
                )
            else:
                task.status = TaskStatus.FAILED

    def _enrich_input(self, task: TaskNode, plan: ExecutionPlan) -> str:
        """Prepend dependency results to the task input."""
        if not task.dependencies:
            return task.input

        parts: list[str] = ["Context from previous tasks:"]
        for dep_id in task.dependencies:
            dep = plan.get_task(dep_id)
            if dep and dep.result:
                parts.append(f"[{dep_id}] {dep.result}")
        parts.append("")
        parts.append(f"Your task: {task.input}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def synthesize(self, plan: ExecutionPlan) -> str:
        """Produce a final answer from the completed plan."""
        completed = [t for t in plan.tasks if t.status == TaskStatus.COMPLETED]
        if not completed:
            return "All tasks failed. No results to synthesize."

        if len(completed) == 1:
            return completed[0].result or ""

        results_block = "\n\n".join(
            f"[{t.id} / {t.agent}]:\n{t.result}" for t in completed
        )
        user_prompt = SYNTHESIZE_USER_TEMPLATE.format(
            query=plan.query, results_block=results_block
        )

        response = await self.router.send(
            [{"role": "user", "content": user_prompt}],
            system=SYNTHESIZE_SYSTEM_PROMPT,
            provider=self.planner_provider,
            model=self.planner_model,
            temperature=0.3,
            max_tokens=4096,
        )
        return response.content

    # ------------------------------------------------------------------
    # High-level entry point
    # ------------------------------------------------------------------

    async def run(self, query: str) -> str:
        """Plan, execute, and synthesize — full pipeline."""
        plan = await self.plan(query)
        plan = await self.execute(plan)

        if plan.has_failures():
            logger.warning(
                "Plan has failures, attempting re-plan for failed tasks"
            )
            plan = await self._replan_failures(plan)
            plan = await self.execute(plan)

        return await self.synthesize(plan)

    async def _replan_failures(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Re-plan failed tasks: reset them as pending with incremented retry."""
        for task in plan.tasks:
            if task.status == TaskStatus.FAILED:
                # Try with a different phrasing
                task.input = (
                    f"(Retry) Previous attempt failed: {task.error}\n"
                    f"Original task: {task.input}"
                )
                task.status = TaskStatus.PENDING
                task.error = None
                task.retries += 1
            elif task.status == TaskStatus.SKIPPED:
                task.status = TaskStatus.PENDING
                task.error = None
        return plan
