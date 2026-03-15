"""Moteur d'orchestration multi-agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import StrEnum

from mascarade.agents.registry import AgentRegistry
from mascarade.cluster import ClusterManager
from mascarade.observability import AgentTraceBuffer, new_run_id
from mascarade.orchestrator.circuit_breaker import CircuitBreaker
from mascarade.orchestrator.dead_letter import DeadLetterStore
from mascarade.orchestrator.retry import RetryConfig, RetryExecutor
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
    remote: bool = False
    selected_by: str = "local-direct"
    peer_id: str | None = None
    node_id: str | None = None
    role: str | None = None
    fallback_used: bool = False
    fallback_agent: str | None = None


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
    cluster: ClusterManager | None = None
    retry_executor: RetryExecutor = field(default_factory=RetryExecutor)
    circuit_breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    dead_letter_store: DeadLetterStore = field(default_factory=DeadLetterStore)

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
        routing_role: str | None = None,
        routing_provider: str | None = None,
        routing_model: str | None = None,
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
            routing_role=routing_role,
            routing_provider=routing_provider,
            routing_model=routing_model,
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
        routing_overrides: dict[str, dict[str, str | None]] | None = None,
        skip_on_error: bool = False,
    ) -> list[TaskResult]:
        """Exécuter des agents séquentiellement, chacun avec le prompt original."""
        results = []
        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            override = (routing_overrides or {}).get(name) or {}
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=i,
                agent_name=name,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_input",
                step=i,
                agent_name=name,
                prompt_excerpt=prompt,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
            )
            try:
                result = await self._execute_agent(
                    agent,
                    prompt,
                    step=i,
                    routing_override=override,
                )
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="agent_output",
                    step=i,
                    agent_name=name,
                    content_excerpt=result.response.content,
                    provider=result.response.provider,
                    model=result.response.model,
                    token_usage=result.response.usage,
                )
                results.append(result)
            except Exception as exc:
                error_msg = str(exc)
                logger.error("Sequential agent %s (step %d) failed: %s", name, i, error_msg)
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="run_failed",
                    step=i,
                    severity="error",
                    agent_name=name,
                    error=error_msg,
                )
                self.dead_letter_store.record_failure(
                    run_id=run_id,
                    error=error_msg,
                    context={"prompt": prompt, "agent_names": agent_names},
                    mode=mode.value,
                    agent_name=name,
                    step=i,
                )
                results.append(TaskResult(agent_name=name, response=LLMResponse(content="", model="", provider="", usage={}), step=i, error=error_msg))
                if not skip_on_error:
                    break
        return results

    async def run_parallel(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        run_id: str,
        mode: ExecutionMode,
        routing_overrides: dict[str, dict[str, str | None]] | None = None,
        timeout: float = 120.0,
    ) -> list[TaskResult]:
        """Exécuter des agents en parallèle sur le même prompt."""

        async def _run_one(name: str, step: int) -> TaskResult:
            agent = self.registry.get(name)
            override = (routing_overrides or {}).get(name) or {}
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=step,
                agent_name=name,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_input",
                step=step,
                agent_name=name,
                prompt_excerpt=prompt,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
            )
            result = await self._execute_agent(
                agent,
                prompt,
                step=step,
                routing_override=override,
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_output",
                step=step,
                agent_name=name,
                content_excerpt=result.response.content,
                provider=result.response.provider,
                model=result.response.model,
                token_usage=result.response.usage,
            )
            return result

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
                self.dead_letter_store.record_failure(
                    run_id=run_id,
                    error=error_msg,
                    context={"prompt": prompt, "agent_names": agent_names},
                    mode=mode.value,
                    agent_name=agent_names[i],
                    step=i,
                )
                results.append(TaskResult(agent_name=agent_names[i], response=LLMResponse(content="", model="", provider="", usage={}), step=i, error=error_msg))
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
        routing_overrides: dict[str, dict[str, str | None]] | None = None,
        skip_on_error: bool = False,
    ) -> list[TaskResult]:
        """Pipeline : la sortie d'un agent devient l'entrée du suivant."""
        results = []
        current_input = initial_prompt

        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            override = (routing_overrides or {}).get(name) or {}
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=i,
                agent_name=name,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_input",
                step=i,
                agent_name=name,
                prompt_excerpt=current_input,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
            )
            try:
                result = await self._execute_agent(
                    agent,
                    current_input,
                    step=i,
                    routing_override=override,
                )
            except Exception as exc:
                error_msg = str(exc)
                logger.error("Pipeline agent %s (step %d) failed: %s", name, i, error_msg)
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="run_failed",
                    step=i,
                    severity="error",
                    agent_name=name,
                    error=error_msg,
                )
                self.dead_letter_store.record_failure(
                    run_id=run_id,
                    error=error_msg,
                    context={"initial_prompt": initial_prompt, "current_input": current_input, "agent_names": agent_names},
                    mode=mode.value,
                    agent_name=name,
                    step=i,
                )
                results.append(TaskResult(agent_name=name, response=LLMResponse(content="", model="", provider="", usage={}), step=i, error=error_msg))
                if not skip_on_error:
                    break
                # Continue with current input if skipping error
                continue
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_output",
                step=i,
                agent_name=name,
                content_excerpt=result.response.content,
                provider=result.response.provider,
                model=result.response.model,
                token_usage=result.response.usage,
            )
            results.append(result)
            if i < len(agent_names) - 1:
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="handoff",
                    step=i,
                    from_agent=name,
                    to_agent=agent_names[i + 1],
                    content_excerpt=result.response.content,
                )
            current_input = result.response.content

        return results

    async def _execute_agent(
        self,
        agent,
        prompt: str,
        *,
        step: int,
        routing_override: dict[str, str | None] | None = None,
    ) -> TaskResult:
        """Exécuter un agent avec retry automatique en cas d'erreur."""

        async def _do_execute() -> TaskResult:
            """Logique d'exécution à retrier."""
            payload = agent.build_send_payload(prompt)
            if routing_override:
                if routing_override.get("preferred_provider"):
                    payload["provider"] = routing_override["preferred_provider"]
                if routing_override.get("preferred_model"):
                    payload["model"] = routing_override["preferred_model"]

            preferred_role = (routing_override or {}).get("preferred_role") or getattr(
                agent, "preferred_role", None
            )

            if self.cluster is not None and self.cluster.enabled:
                routed = await self.cluster.forward_send(
                    peer_id=None,
                    preferred_role=preferred_role,
                    allow_local=True,
                    payload=payload,
                )
                response = LLMResponse(
                    content=str(routed["content"]),
                    model=str(routed["model"]),
                    provider=str(routed["provider"]),
                    usage=dict(routed.get("usage") or {}),
                )
                return TaskResult(
                    agent_name=agent.name,
                    response=response,
                    step=step,
                    remote=bool(routed.get("remote")),
                    selected_by=str(routed.get("selected_by") or "cluster"),
                    peer_id=routed.get("peer_id"),
                    node_id=routed.get("node_id") or None,
                    role=str(routed.get("role") or "") or None,
                )

            response = await self.router.send(
                payload["messages"],
                strategy=payload["strategy"],
                provider=payload["provider"],
                model=payload["model"],
                system=payload["system"],
                temperature=payload["temperature"],
                max_tokens=payload["max_tokens"],
            )
            return TaskResult(
                agent_name=agent.name,
                response=response,
                step=step,
                remote=False,
                selected_by="local-direct",
                node_id=None,
                role=None,
            )

        # Exécuter avec retry
        return await self.retry_executor.execute_with_retry(
            _do_execute,
            agent_name=agent.name,
        )

    async def run(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        mode: ExecutionMode | str = ExecutionMode.SEQUENTIAL,
        routing_overrides: dict[str, dict[str, str | None]] | None = None,
        skip_on_error: bool = False,
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
                    routing_overrides=routing_overrides,
                    skip_on_error=skip_on_error,
                )
            elif mode == ExecutionMode.PARALLEL:
                results = await self.run_parallel(
                    agent_names,
                    prompt,
                    run_id=run_id,
                    mode=mode,
                    routing_overrides=routing_overrides,
                )
            else:
                results = await self.run_pipeline(
                    agent_names,
                    prompt,
                    run_id=run_id,
                    mode=mode,
                    routing_overrides=routing_overrides,
                    skip_on_error=skip_on_error,
                )
        except Exception as exc:
            error_msg = str(exc)
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="run_failed",
                step=-1,
                severity="error",
                error=error_msg,
            )
            self.dead_letter_store.record_failure(
                run_id=run_id,
                error=error_msg,
                context={"prompt": prompt, "agent_names": agent_names, "mode": mode.value},
                mode=mode.value,
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
