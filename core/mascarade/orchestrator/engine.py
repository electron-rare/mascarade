"""Moteur d'orchestration multi-agents."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mascarade.agents.registry import AgentRegistry
from mascarade.cluster import ClusterManager
from mascarade.config import settings
from mascarade.observability import AgentTraceBuffer, new_run_id
from mascarade.orchestrator.circuit_breaker import CircuitBreaker
from mascarade.orchestrator.dead_letter import DeadLetterStore
from mascarade.orchestrator.retry import RetryConfig, RetryExecutor
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse

logger = logging.getLogger("mascarade.orchestrator")


def _env_float(
    name: str, default: float, *, min_value: float, max_value: float
) -> float:
    raw = str(os.getenv(name, str(default))).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default
    return max(min_value, min(value, max_value))


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = str(os.getenv(name, str(default))).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(min_value, min(value, max_value))


_RAY_EXEC_TIMEOUT_S = _env_float(
    "ORCHESTRATOR_RAY_EXEC_TIMEOUT_S",
    45.0,
    min_value=5.0,
    max_value=300.0,
)
_RAY_CIRCUIT_FAILURE_THRESHOLD = _env_int(
    "ORCHESTRATOR_RAY_CIRCUIT_FAILURE_THRESHOLD",
    3,
    min_value=1,
    max_value=20,
)
_RAY_CIRCUIT_COOLDOWN_S = _env_float(
    "ORCHESTRATOR_RAY_CIRCUIT_COOLDOWN_S",
    60.0,
    min_value=5.0,
    max_value=3600.0,
)


def _ray_router_send(payload: dict[str, Any]) -> dict[str, Any]:
    """Worker Ray: exécute un appel Router.send isolé."""
    from mascarade.router import Router as WorkerRouter
    from mascarade.router.router import Strategy

    strategy = Strategy(str(payload["strategy"]))
    response = asyncio.run(
        WorkerRouter().send(
            payload["messages"],
            strategy=strategy,
            routing_policy=payload.get("routing_policy"),
            provider=payload.get("provider"),
            model=payload.get("model"),
            system=payload.get("system"),
            temperature=payload.get("temperature"),
            max_tokens=payload.get("max_tokens"),
            project_id=payload.get("project_id"),
            federation_scope=payload.get("federation_scope"),
            knowledge_scope=payload.get("knowledge_scope", "project"),
        )
    )
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": dict(response.usage or {}),
    }


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
    transport: str | None = None
    latency_ms: int | None = None
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
    skill_registry: Any = None
    trace_buffer: AgentTraceBuffer | None = None
    cluster: ClusterManager | None = None
    retry_executor: RetryExecutor = field(
        default_factory=lambda: RetryExecutor(config=RetryConfig())
    )
    dead_letter_store: DeadLetterStore = field(default_factory=DeadLetterStore)
    circuit_breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    _ray_client: Any = field(default=None, init=False, repr=False)
    _ray_send_remote: Any = field(default=None, init=False, repr=False)
    _ray_disabled: bool = field(default=False, init=False, repr=False)
    _ray_failures: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _ray_circuit_open_until: dict[str, float] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.trace_buffer is None:
            self.trace_buffer = AgentTraceBuffer()

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
        routing_policy: str | None = None,
        routing_selected_by: str | None = None,
        routing_transport: str | None = None,
        routing_latency_ms: float | None = None,
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
            routing_policy=routing_policy,
            routing_selected_by=routing_selected_by,
            routing_transport=routing_transport,
            routing_latency_ms=routing_latency_ms,
            token_usage=token_usage,
            error=error,
        )

    async def _ensure_ray(self) -> Any | None:
        if not settings.orchestrator_ray_enabled or self._ray_disabled:
            return None
        if self._ray_client is not None:
            return self._ray_client
        try:
            import ray
        except Exception as exc:  # pragma: no cover - dépend de l'env runtime
            logger.warning("Ray indisponible, fallback local: %s", exc)
            self._ray_disabled = True
            return None

        def _init_ray() -> Any:
            if not ray.is_initialized():
                ray.init(
                    address=settings.orchestrator_ray_address,
                    namespace=settings.orchestrator_ray_namespace,
                    ignore_reinit_error=True,
                    log_to_driver=False,
                )
            return ray

        try:
            self._ray_client = await asyncio.to_thread(_init_ray)
            self._ray_send_remote = self._ray_client.remote(_ray_router_send)
            logger.info(
                "Ray orchestrator activé (address=%s, namespace=%s)",
                settings.orchestrator_ray_address,
                settings.orchestrator_ray_namespace,
            )
            return self._ray_client
        except Exception as exc:
            logger.warning("Init Ray échouée, fallback local: %s", exc)
            self._ray_disabled = True
            return None

    async def _execute_agent_via_ray(
        self,
        *,
        agent_name: str,
        payload: dict[str, Any],
        step: int,
    ) -> TaskResult | None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        open_until = self._ray_circuit_open_until.get(agent_name, 0.0)
        if open_until > now:
            remaining = max(0.0, open_until - now)
            logger.warning(
                "Circuit Ray ouvert pour %s (cooldown %.1fs restant), fallback local",
                agent_name,
                remaining,
            )
            return None
        if open_until and open_until <= now:
            self._ray_circuit_open_until.pop(agent_name, None)
            self._ray_failures.pop(agent_name, None)

        ray_client = await self._ensure_ray()
        if ray_client is None or self._ray_send_remote is None:
            return None

        start = loop.time()
        ray_payload = {
            "messages": payload["messages"],
            "strategy": str(payload["strategy"]),
            "routing_policy": payload.get("routing_policy"),
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "system": payload.get("system"),
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
            "project_id": payload.get("project_id"),
            "federation_scope": payload.get("federation_scope"),
            "knowledge_scope": payload.get("knowledge_scope", "project"),
        }
        try:
            routed = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: ray_client.get(
                        self._ray_send_remote.remote(ray_payload),
                        timeout=_RAY_EXEC_TIMEOUT_S,
                    )
                ),
                timeout=_RAY_EXEC_TIMEOUT_S + 2.0,
            )
        except Exception as exc:
            logger.warning(
                "Exécution Ray échouée pour %s, fallback local: %s", agent_name, exc
            )
            failure_count = int(self._ray_failures.get(agent_name, 0)) + 1
            self._ray_failures[agent_name] = failure_count
            if failure_count >= _RAY_CIRCUIT_FAILURE_THRESHOLD:
                self._ray_circuit_open_until[agent_name] = now + _RAY_CIRCUIT_COOLDOWN_S
                logger.warning(
                    "Circuit Ray ouvert pour %s après %d échecs (cooldown %.1fs)",
                    agent_name,
                    failure_count,
                    _RAY_CIRCUIT_COOLDOWN_S,
                )
            return None

        self._ray_failures.pop(agent_name, None)
        self._ray_circuit_open_until.pop(agent_name, None)
        response = LLMResponse(
            content=str(routed["content"]),
            model=str(routed["model"]),
            provider=str(routed["provider"]),
            usage=dict(routed.get("usage") or {}),
        )
        latency_ms = int((loop.time() - start) * 1000)
        return TaskResult(
            agent_name=agent_name,
            response=response,
            step=step,
            remote=True,
            selected_by="orchestrator-ray",
            node_id=None,
            role=None,
            transport="ray",
            latency_ms=latency_ms,
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
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[TaskResult]:
        """Exécuter des agents séquentiellement, chacun avec le prompt original."""
        results = []
        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            override = (routing_overrides or {}).get(name) or {}
            routing_policy = override.get("routing_policy") or getattr(
                agent, "routing_policy", None
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=i,
                agent_name=name,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
                routing_policy=routing_policy,
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
                routing_policy=routing_policy,
            )
            try:
                result = await self._execute_agent(
                    agent,
                    prompt,
                    step=i,
                    routing_override=override,
                    run_id=run_id,
                    mode=mode,
                    project_id=project_id,
                    federation_scope=federation_scope,
                    knowledge_scope=knowledge_scope,
                )
            except Exception as exc:
                error_msg = str(exc)
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
                result = TaskResult(
                    agent_name=name,
                    response=LLMResponse(content="", model="", provider="", usage={}),
                    step=i,
                    error=error_msg,
                )
                results.append(result)
                if not skip_on_error:
                    break
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
                routing_policy=routing_policy,
                routing_selected_by=result.selected_by,
                routing_transport=result.transport,
                routing_latency_ms=result.latency_ms,
                token_usage=result.response.usage,
            )
            results.append(result)
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
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[TaskResult]:
        """Exécuter des agents en parallèle sur le même prompt."""

        async def _run_one(name: str, step: int) -> TaskResult:
            agent = self.registry.get(name)
            override = (routing_overrides or {}).get(name) or {}
            routing_policy = override.get("routing_policy") or getattr(
                agent, "routing_policy", None
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=step,
                agent_name=name,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
                routing_policy=routing_policy,
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
                routing_policy=routing_policy,
            )
            result = await self._execute_agent(
                agent,
                prompt,
                step=step,
                routing_override=override,
                run_id=run_id,
                mode=mode,
                project_id=project_id,
                federation_scope=federation_scope,
                knowledge_scope=knowledge_scope,
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
                routing_policy=routing_policy,
                routing_selected_by=result.selected_by,
                routing_transport=result.transport,
                routing_latency_ms=result.latency_ms,
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
                results.append(
                    TaskResult(
                        agent_name=agent_names[i],
                        response=LLMResponse(
                            content="", model="", provider="", usage={}
                        ),
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
        routing_overrides: dict[str, dict[str, str | None]] | None = None,
        skip_on_error: bool = False,
        fallback_map: dict[str, str] | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[TaskResult]:
        """Pipeline : la sortie d'un agent devient l'entrée du suivant.

        Args:
            agent_names: List of agent names to execute sequentially
            initial_prompt: Initial prompt
            run_id: Unique ID for this run
            mode: Execution mode
            routing_overrides: Optional routing overrides per agent
            skip_on_error: Continue pipeline even if stage fails (after trying fallback)
            fallback_map: Optional mapping of agent_name -> fallback_agent_name
                         When primary agent fails, fallback agent is attempted
        """
        results = []
        current_input = initial_prompt

        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            override = (routing_overrides or {}).get(name) or {}
            fallback_name = (fallback_map or {}).get(name)
            routing_policy = override.get("routing_policy") or getattr(
                agent, "routing_policy", None
            )
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="step_started",
                step=i,
                agent_name=name,
                routing_role=override.get("preferred_role"),
                routing_provider=override.get("preferred_provider"),
                routing_model=override.get("preferred_model"),
                routing_policy=routing_policy,
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
                routing_policy=routing_policy,
            )
            try:
                result = await self._execute_agent(
                    agent,
                    current_input,
                    step=i,
                    routing_override=override,
                    run_id=run_id,
                    mode=mode,
                    project_id=project_id,
                    federation_scope=federation_scope,
                    knowledge_scope=knowledge_scope,
                )
            except Exception as exc:
                error_msg = str(exc)
                if fallback_name:
                    self._trace(
                        run_id=run_id,
                        mode=mode,
                        event_type="fallback_triggered",
                        step=i,
                        severity="warning",
                        agent_name=name,
                        error=f"Primary agent '{name}' failed, trying fallback '{fallback_name}'",
                    )
                    try:
                        fallback_agent = self.registry.get(fallback_name)
                        fallback_override = (routing_overrides or {}).get(
                            fallback_name
                        ) or {}
                        result = await self._execute_agent(
                            fallback_agent,
                            current_input,
                            step=i,
                            routing_override=fallback_override,
                            run_id=run_id,
                            mode=mode,
                            project_id=project_id,
                            federation_scope=federation_scope,
                            knowledge_scope=knowledge_scope,
                        )
                        result.fallback_used = True
                        result.fallback_agent = fallback_name
                        self._trace(
                            run_id=run_id,
                            mode=mode,
                            event_type="agent_output",
                            step=i,
                            agent_name=fallback_name,
                            content_excerpt=result.response.content,
                            provider=result.response.provider,
                            model=result.response.model,
                            routing_policy=routing_policy,
                            routing_selected_by=result.selected_by,
                            routing_transport=result.transport,
                            routing_latency_ms=result.latency_ms,
                            token_usage=result.response.usage,
                        )
                        results.append(result)
                        current_input = result.response.content
                        continue
                    except Exception as fallback_exc:
                        error_msg = (
                            f"Primary agent '{name}' failed: {exc}; "
                            f"Fallback agent '{fallback_name}' also failed: {fallback_exc}"
                        )
                logger.error(
                    "Pipeline agent %s (step %d) failed: %s", name, i, error_msg
                )
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
                    context={
                        "initial_prompt": initial_prompt,
                        "current_input": current_input,
                        "agent_names": agent_names,
                    },
                    mode=mode.value,
                    agent_name=name,
                    step=i,
                )
                results.append(
                    TaskResult(
                        agent_name=name,
                        response=LLMResponse(
                            content="", model="", provider="", usage={}
                        ),
                        step=i,
                        error=error_msg,
                        fallback_used=False,
                        fallback_agent=fallback_name,
                    )
                )
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
                routing_policy=routing_policy,
                routing_selected_by=result.selected_by,
                routing_transport=result.transport,
                routing_latency_ms=result.latency_ms,
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
        run_id: str | None = None,
        mode: ExecutionMode | None = None,
        fallback_agent_name: str | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> TaskResult:
        payload = agent.build_send_payload(
            prompt,
            skill_registry=self.skill_registry,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )
        if routing_override:
            if routing_override.get("preferred_provider"):
                payload["provider"] = routing_override["preferred_provider"]
            if routing_override.get("preferred_model"):
                payload["model"] = routing_override["preferred_model"]
            if routing_override.get("routing_policy"):
                payload["routing_policy"] = routing_override["routing_policy"]
        if settings.routellm_enabled and not payload.get("provider"):
            strategy_raw = str(payload.get("strategy") or "").strip().lower()
            policy_raw = str(payload.get("routing_policy") or "").strip().lower()
            if strategy_raw in {"best", "cheapest", "fastest", "routellm"}:
                payload["strategy"] = "routellm"
                if policy_raw not in {"auto", "strong", "cheap", "fast"}:
                    if strategy_raw == "cheapest":
                        payload["routing_policy"] = "cheap"
                    elif strategy_raw == "fastest":
                        payload["routing_policy"] = "fast"
                    elif strategy_raw == "best":
                        payload["routing_policy"] = "strong"
                    else:
                        payload["routing_policy"] = "auto"

        # Obtenir ou créer le circuit breaker pour cet agent
        if agent.name not in self.circuit_breakers:
            breaker = CircuitBreaker()
            # Configurer le callback pour les changements d'état
            if run_id and mode:
                breaker.on_state_change = lambda old_state, new_state: self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="circuit_breaker_state_changed",
                    step=step,
                    severity="warning",
                    agent_name=agent.name,
                    error=f"Circuit breaker transitioned from {old_state} to {new_state}",
                )
            self.circuit_breakers[agent.name] = breaker

        breaker = self.circuit_breakers[agent.name]

        # Vérifier si le circuit breaker autorise l'exécution
        if not breaker.can_execute():
            error_msg = f"Circuit breaker is {breaker.state} for agent {agent.name}"
            logger.warning(error_msg)
            if run_id and mode:
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="circuit_breaker_blocked",
                    step=step,
                    severity="warning",
                    agent_name=agent.name,
                    error=error_msg,
                )
            raise RuntimeError(error_msg)

        async def _do_execute() -> TaskResult:
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
                    node_id=str(routed.get("node_id") or "") or None,
                    role=str(routed.get("role") or "") or None,
                    transport=str(
                        routed.get("transport")
                        or ("local" if not routed.get("remote") else "")
                    )
                    or None,
                    latency_ms=(
                        int(routed["latency_ms"])
                        if isinstance(routed.get("latency_ms"), (int, float))
                        else None
                    ),
                )

            ray_result = await self._execute_agent_via_ray(
                agent_name=agent.name,
                payload=payload,
                step=step,
            )
            if ray_result is not None:
                return ray_result

            response = await self.router.send(
                payload["messages"],
                strategy=payload["strategy"],
                routing_policy=payload.get("routing_policy"),
                provider=payload["provider"],
                model=payload["model"],
                system=payload["system"],
                temperature=payload["temperature"],
                max_tokens=payload["max_tokens"],
                project_id=payload.get("project_id"),
                federation_scope=payload.get("federation_scope"),
                knowledge_scope=str(payload.get("knowledge_scope") or "project"),
            )
            return TaskResult(
                agent_name=agent.name,
                response=response,
                step=step,
                remote=False,
                selected_by="local-direct",
                node_id=None,
                role=preferred_role,
                transport="local",
                latency_ms=0,
                fallback_used=bool(fallback_agent_name),
                fallback_agent=fallback_agent_name,
            )

        def _on_retry(attempt: int, error: str, delay: float) -> None:
            if run_id and mode:
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    event_type="retry_attempt",
                    step=step,
                    severity="warning",
                    agent_name=agent.name,
                    error=f"attempt={attempt} delay={delay:.2f}s error={error}",
                )

        try:
            result = await self.retry_executor.execute_with_retry(
                _do_execute,
                agent_name=agent.name,
                on_retry=_on_retry,
            )
            breaker.record_success()
            return result
        except Exception:
            breaker.record_failure()
            raise

    async def run(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        mode: ExecutionMode | str = ExecutionMode.SEQUENTIAL,
        routing_overrides: dict[str, dict[str, str | None]] | None = None,
        skip_on_error: bool = False,
        fallback_map: dict[str, str] | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
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
                    project_id=project_id,
                    federation_scope=federation_scope,
                    knowledge_scope=knowledge_scope,
                )
            elif mode == ExecutionMode.PARALLEL:
                results = await self.run_parallel(
                    agent_names,
                    prompt,
                    run_id=run_id,
                    mode=mode,
                    routing_overrides=routing_overrides,
                    project_id=project_id,
                    federation_scope=federation_scope,
                    knowledge_scope=knowledge_scope,
                )
            else:
                results = await self.run_pipeline(
                    agent_names,
                    prompt,
                    run_id=run_id,
                    mode=mode,
                    routing_overrides=routing_overrides,
                    skip_on_error=skip_on_error,
                    fallback_map=fallback_map,
                    project_id=project_id,
                    federation_scope=federation_scope,
                    knowledge_scope=knowledge_scope,
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
                context={
                    "prompt": prompt,
                    "agent_names": agent_names,
                    "mode": mode.value,
                },
                mode=mode.value,
            )
            raise

        if any(result.error for result in results):
            error_summary = "; ".join(
                result.error or "" for result in results if result.error
            )
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
