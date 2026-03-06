"""Moteur d'orchestration multi-agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import StrEnum

from mascarade.agents.registry import AgentRegistry
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
class Orchestrator:
    """Orchestrateur multi-agents — séquentiel, parallèle, ou pipeline."""

    router: Router = field(default_factory=Router)
    registry: AgentRegistry = field(default_factory=AgentRegistry)

    async def run_sequential(
        self,
        agent_names: list[str],
        prompt: str,
    ) -> list[TaskResult]:
        """Exécuter des agents séquentiellement, chacun avec le prompt original."""
        results = []
        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            response = await agent.run(prompt, router=self.router)
            results.append(TaskResult(agent_name=name, response=response, step=i))
        return results

    async def run_parallel(
        self,
        agent_names: list[str],
        prompt: str,
    ) -> list[TaskResult]:
        """Exécuter des agents en parallèle sur le même prompt."""

        async def _run_one(name: str, step: int) -> TaskResult:
            agent = self.registry.get(name)
            response = await agent.run(prompt, router=self.router)
            return TaskResult(agent_name=name, response=response, step=step)

        tasks = [_run_one(name, i) for i, name in enumerate(agent_names)]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[TaskResult] = []
        for i, r in enumerate(raw_results):
            if isinstance(r, BaseException):
                logger.error("Agent %s failed: %s", agent_names[i], r)
                results.append(
                    TaskResult(
                        agent_name=agent_names[i],
                        response=LLMResponse(
                            content="", model="", provider="", usage={}
                        ),
                        step=i,
                        error=str(r),
                    )
                )
            else:
                results.append(r)
        return results

    async def run_pipeline(
        self,
        agent_names: list[str],
        initial_prompt: str,
    ) -> list[TaskResult]:
        """Pipeline : la sortie d'un agent devient l'entrée du suivant."""
        results = []
        current_input = initial_prompt

        for i, name in enumerate(agent_names):
            agent = self.registry.get(name)
            response = await agent.run(current_input, router=self.router)
            results.append(TaskResult(agent_name=name, response=response, step=i))
            current_input = response.content

        return results

    async def run(
        self,
        agent_names: list[str],
        prompt: str,
        *,
        mode: ExecutionMode | str = ExecutionMode.SEQUENTIAL,
    ) -> list[TaskResult]:
        """Point d'entrée principal — choisir le mode d'exécution."""
        mode = ExecutionMode(mode)
        if mode == ExecutionMode.SEQUENTIAL:
            return await self.run_sequential(agent_names, prompt)
        elif mode == ExecutionMode.PARALLEL:
            return await self.run_parallel(agent_names, prompt)
        else:
            return await self.run_pipeline(agent_names, prompt)
