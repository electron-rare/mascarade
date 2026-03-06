"""Moteur d'orchestration multi-agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import StrEnum

from mascarade.agents.registry import AgentRegistry
from mascarade.observability import AgentTraceBuffer, new_run_id
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse

logger = logging.getLogger("mascarade.orchestrator")


class ExecutionMode(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"


@dataclass
class TaskResult:
    agent_name: str
    response: LLMResponse
    step: int = 0
    error: str | None = None


@dataclass
class OrchestrationRun:
    run_id: str
    mode: ExecutionMode
    results: list[TaskResult]


@dataclass
class Orchestrator:
    """Orchestrateur multi-agents — séquentiel, parallèle, ou pipeline."""

    router: Router = field(default_factory=Router)
    registry: AgentRegistry = field(default_factory=AgentRegistry)
    trace_buffer: AgentTraceBuffer | None = None

    def _trace(
        self,
        *,
        run_id: str,
        mode: ExecutionMode,
        event_type: str,
        step: int,
        severity: str = "info",
        agent_name: str | None = None,
        from_agent: str | None = None,
        to_agent: str | None = None,
        prompt_excerpt: str | None = None,
        content_excerpt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        token_usage: dict[str, int] | None = None,
        error: str | None = None,
    ) -> None:
        if self.trace_buffer is None:
            return

        self.trace_buffer.record(
            run_id=run_id,
            mode=mode.value,
            event_type=event_type,
            step=step,
            severity=severity,
            agent_name=agent_name,
            from_agent=from_agent,
            to_agent=to_agent,
            prompt_excerpt=prompt_excerpt,
            content_excerpt=content_excerpt,
            provider=provider,
            model=model,
            token_usage=token_usage,
            error=error,
        )

    async def run_sequential(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        run_id: str,
        mode: ExecutionMode,
    ) -> list[TaskResult]:
        """Exécuter des agents séquentiellement, chacun avec le prompt original."""
        results = []
        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=i,
                agent_name=name,
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_input",
                step=i,
                agent_name=name,
                prompt_excerpt=prompt,
            )
            response = await agent.run(prompt, router=self.router)
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_output",
                step=i,
                agent_name=name,
                content_excerpt=response.content,
                provider=response.provider,
                model=response.model,
                token_usage=response.usage,
            )
            results.append(TaskResult(agent_name=name, response=response, step=i))
        return results

    async def run_parallel(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        run_id: str,
        mode: ExecutionMode,
        timeout: float = 120.0,
    ) -> list[TaskResult]:
        """Exécuter des agents en parallèle sur le même prompt."""

        async def _run_one(name: str, step: int) -> TaskResult:
            agent = self.registry.get(name)
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=step,
                agent_name=name,
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_input",
                step=step,
                agent_name=name,
                prompt_excerpt=prompt,
            )
            response = await agent.run(prompt, router=self.router)
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_output",
                step=step,
                agent_name=name,
                content_excerpt=response.content,
                provider=response.provider,
                model=response.model,
                token_usage=response.usage,
            )
            return TaskResult(agent_name=name, response=response, step=step)

        tasks = [_run_one(name, i) for i, name in enumerate(agent_names)]
        raw_results = await asyncio.gather(
            *[asyncio.wait_for(t, timeout=timeout) for t in tasks],
            return_exceptions=True,
        )

        results: list[TaskResult] = []
        for i, r in enumerate(raw_results):
            if isinstance(r, BaseException):
                error_msg = str(r)
                if isinstance(r, asyncio.TimeoutError):
                    error_msg = f"Agent timed out after {timeout}s"
                logger.error("Agent %s failed: %s", agent_names[i], error_msg)
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="run_failed",
                    step=i,
                    severity="error",
                    agent_name=agent_names[i],
                    error=error_msg,
                )
                results.append(
                    TaskResult(
                        agent_name=agent_names[i],
                        response=LLMResponse(content="", model="", provider="", usage={}),
                        step=i,
                        error=error_msg,
                    )
                )
            else:
                results.append(r)
        return results

    async def run_pipeline(
        self,
        agent_names: list[str],
        initial_prompt: str,
        *,
        run_id: str,
        mode: ExecutionMode,
    ) -> list[TaskResult]:
        """Pipeline : la sortie d'un agent devient l'entrée du suivant."""
        results = []
        current_input = initial_prompt

        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=i,
                agent_name=name,
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_input",
                step=i,
                agent_name=name,
                prompt_excerpt=current_input,
            )
            try:
                response = await agent.run(current_input, router=self.router)
            except Exception as exc:
                logger.error("Pipeline agent %s (step %d) failed: %s", name, i, exc)
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="run_failed",
                    step=i,
                    severity="error",
                    agent_name=name,
                    error=str(exc),
                )
                results.append(
                    TaskResult(
                        agent_name=name,
                        response=LLMResponse(content="", model="", provider="", usage={}),
                        step=i,
                        error=str(exc),
                    )
                )
                break
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_output",
                step=i,
                agent_name=name,
                content_excerpt=response.content,
                provider=response.provider,
                model=response.model,
                token_usage=response.usage,
            )
            results.append(TaskResult(agent_name=name, response=response, step=i))
            if i < len(agent_names) - 1:
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="handoff",
                    step=i,
                    from_agent=name,
                    to_agent=agent_names[i + 1],
                    content_excerpt=response.content,
                )
            current_input = response.content

        return results

    async def run(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        mode: ExecutionMode | str = ExecutionMode.SEQUENTIAL,
    ) -> OrchestrationRun:
        """Point d'entrée principal — choisir le mode d'exécution."""
        mode = ExecutionMode(mode)
        run_id = new_run_id()
        self._trace(
            run_id=run_id,
            mode=mode,
            event_type="run_started",
            step=-1,
            agent_name=",".join(agent_names),
            prompt_excerpt=prompt,
        )

        try:
            if mode == ExecutionMode.SEQUENTIAL:
                results = await self.run_sequential(
                    agent_names,
                    prompt,
                    run_id=run_id,
                    mode=mode,
                )
            elif mode == ExecutionMode.PARALLEL:
                results = await self.run_parallel(
                    agent_names,
                    prompt,
                    run_id=run_id,
                    mode=mode,
                )
            else:
                results = await self.run_pipeline(
                    agent_names,
                    prompt,
                    run_id=run_id,
                    mode=mode,
                )
        except Exception as exc:
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="run_failed",
                step=-1,
                severity="error",
                error=str(exc),
            )
            raise

        if any(result.error for result in results):
            error_summary = "; ".join(result.error or "" for result in results if result.error)
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="run_failed",
                step=max((result.step for result in results), default=-1),
                severity="error",
                error=error_summary,
            )
        else:
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="run_completed",
                step=max((result.step for result in results), default=-1),
            )

        return OrchestrationRun(run_id=run_id, mode=mode, results=results)
