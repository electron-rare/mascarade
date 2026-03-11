"""Moteur d'orchestration multi-agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mascarade.agents.registry import AgentRegistry
from mascarade.cluster import ClusterManager
from mascarade.config import settings
from mascarade.observability import AgentTraceBuffer, new_run_id
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse

logger = logging.getLogger("mascarade.orchestrator")


def _ray_router_send(payload: dict[str, Any]) -> dict[str, Any]:
    """Worker Ray: exécute un appel Router.send isolé."""
    from mascarade.router import Router as WorkerRouter
    from mascarade.router.router import Strategy

    strategy = Strategy(str(payload["strategy"]))
    response = asyncio.run(
        WorkerRouter().send(
            payload["messages"],
            strategy=strategy,
            provider=payload.get("provider"),
            model=payload.get("model"),
            system=payload.get("system"),
            temperature=payload.get("temperature"),
            max_tokens=payload.get("max_tokens"),
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
    _ray_client: Any = field(default=None, init=False, repr=False)
    _ray_send_remote: Any = field(default=None, init=False, repr=False)
    _ray_disabled: bool = field(default=False, init=False, repr=False)

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
        ray_client = await self._ensure_ray()
        if ray_client is None or self._ray_send_remote is None:
            return None

        loop = asyncio.get_running_loop()
        start = loop.time()
        ray_payload = {
            "messages": payload["messages"],
            "strategy": str(payload["strategy"]),
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "system": payload.get("system"),
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
        }
        try:
            routed = await asyncio.to_thread(
                ray_client.get, self._ray_send_remote.remote(ray_payload)
            )
        except Exception as exc:
            logger.warning("Exécution Ray échouée pour %s, fallback local: %s", agent_name, exc)
            return None

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
                results.append(TaskResult(agent_name=name, response=LLMResponse(content="", model="", provider="", usage={}), step=i, error=str(exc)))
                break
            self._trace(
                run_id=run_id,
                mode=mode,
                event_type="agent_output",
                step=i,
                agent_name=name,
                content_excerpt=result.response.content,
                provider=result.response.provider,
                model=result.response.model,
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
    ) -> TaskResult:
        payload = agent.build_send_payload(prompt)
        if routing_override:
            if routing_override.get("preferred_provider"):
                payload["provider"] = routing_override["preferred_provider"]
            if routing_override.get("preferred_model"):
                payload["model"] = routing_override["preferred_model"]
        if settings.routellm_enabled and not payload.get("provider"):
            strategy_raw = str(payload.get("strategy") or "")
            if strategy_raw in {"best", "cheapest", "fastest", "routellm"}:
                payload["strategy"] = "routellm"

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
                transport=str(routed.get("transport") or ("local" if not routed.get("remote") else "")) or None,
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
            transport="local",
            latency_ms=0,
        )

    async def run(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        mode: ExecutionMode | str = ExecutionMode.SEQUENTIAL,
        routing_overrides: dict[str, dict[str, str | None]] | None = None,
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
