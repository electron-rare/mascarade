"""
Wizard Orchestrator — sequential and parallel agent execution with resilience.

Handles retry, fallback, and aggregation of agent results.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from mascarade.agents.registry import AgentRegistry
from mascarade.agents.wizard_schemas import (
    AggregatedAnalysis,
    ExecutionMetrics,
    ExecutionMode,
    WizardAgentResult,
    WizardExecutionError,
    WizardRunResult,
    WizardRunStatus,
    AgentSelectionStatus,
)
from mascarade.metrics.tracker import MetricsTracker

logger = logging.getLogger("mascarade.wizard")

MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = [2, 4]  # Exponential backoff


class WizardOrchestrator:
    """Orchestrates execution of selected agents with resilience patterns."""

    def __init__(self, registry: AgentRegistry, metrics: Optional[MetricsTracker] = None) -> None:
        self.registry = registry
        self.metrics = metrics or MetricsTracker()

    async def execute(
        self,
        task_id: str,
        selected_agents: list[dict],  # [{"name": "...", ...}, ...]
        task_description: str,
        task_context: dict[str, Any],
        execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        timeout_seconds: float = 120,
        continue_on_error: bool = False,
        fail_on_partial: bool = True,
    ) -> WizardRunResult:
        """Execute selected agents and return aggregated results.

        Args:
            task_id: Unique execution ID
            selected_agents: List of selected agent info dicts
            task_description: Original task description
            task_context: Task-specific context (files, settings, etc.)
            execution_mode: Sequential or parallel
            timeout_seconds: Total timeout for all agents
            continue_on_error: In sequential mode, continue on failure
            fail_on_partial: In parallel mode, fail if any agent fails

        Returns:
            WizardRunResult with all agent results and aggregated analysis
        """
        start_time = datetime.utcnow()
        start_ms = start_time.timestamp() * 1000

        try:
            if execution_mode == ExecutionMode.SEQUENTIAL:
                results = await self._execute_sequential(
                    task_id=task_id,
                    selected_agents=selected_agents,
                    task_description=task_description,
                    task_context=task_context,
                    timeout_seconds=timeout_seconds,
                    continue_on_error=continue_on_error,
                )
            else:  # PARALLEL
                results = await self._execute_parallel(
                    task_id=task_id,
                    selected_agents=selected_agents,
                    task_description=task_description,
                    task_context=task_context,
                    timeout_seconds=timeout_seconds,
                    fail_on_partial=fail_on_partial,
                )

            # Check overall status
            status = self._compute_overall_status(results, fail_on_partial)
            total_cost = sum(
                r.metrics.cost_usd for r in results if r.metrics
            )
            total_duration_ms = (datetime.utcnow().timestamp() * 1000) - start_ms

            # Aggregate analyses
            aggregated = self._aggregate_analyses(results, task_description)

            run_result = WizardRunResult(
                task_id=task_id,
                status=status,
                execution_mode=execution_mode,
                results=results,
                aggregated_analysis=aggregated,
                total_duration_ms=total_duration_ms,
                total_cost_usd=total_cost,
                completion_timestamp=datetime.utcnow(),
                error_reason=self._extract_error_reason(results, status),
            )

            logger.info(
                f"Wizard execution {task_id} completed: {status.value} "
                f"({len(results)} agents, {total_cost:.2f}USD, {total_duration_ms:.0f}ms)"
            )

            return run_result

        except asyncio.TimeoutError:
            logger.error(f"Wizard execution {task_id} timed out after {timeout_seconds}s")
            return WizardRunResult(
                task_id=task_id,
                status=WizardRunStatus.TIMEOUT,
                execution_mode=execution_mode,
                results=[],
                aggregated_analysis=None,
                total_duration_ms=(datetime.utcnow().timestamp() * 1000) - start_ms,
                total_cost_usd=0,
                completion_timestamp=datetime.utcnow(),
                error_reason=f"Execution timed out after {timeout_seconds}s",
            )
        except Exception as e:
            logger.error(f"Wizard execution {task_id} failed: {e}")
            return WizardRunResult(
                task_id=task_id,
                status=WizardRunStatus.FAILED,
                execution_mode=execution_mode,
                results=[],
                aggregated_analysis=None,
                total_duration_ms=(datetime.utcnow().timestamp() * 1000) - start_ms,
                total_cost_usd=0,
                completion_timestamp=datetime.utcnow(),
                error_reason=str(e),
            )

    async def _execute_sequential(
        self,
        task_id: str,
        selected_agents: list[dict],
        task_description: str,
        task_context: dict[str, Any],
        timeout_seconds: float,
        continue_on_error: bool,
    ) -> list[WizardAgentResult]:
        """Execute agents one by one, optionally continuing on error."""
        results = []
        deadline = asyncio.get_event_loop().time() + timeout_seconds

        for agent_info in selected_agents:
            agent_name = agent_info.get("name")

            # Check timeout
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning(f"Sequential execution timeout reached before {agent_name}")
                break

            try:
                result = await self._execute_agent_with_retry(
                    task_id=task_id,
                    agent_name=agent_name,
                    task_description=task_description,
                    task_context=task_context,
                    timeout_seconds=remaining,
                )
                results.append(result)

                if result.status != AgentSelectionStatus.COMPLETED:
                    if not continue_on_error:
                        logger.info(f"Agent {agent_name} failed; stopping sequential execution")
                        break
                    else:
                        logger.info(f"Agent {agent_name} failed; continuing with next agent")

            except asyncio.TimeoutError:
                results.append(
                    WizardAgentResult(
                        task_id=task_id,
                        agent_name=agent_name,
                        status=AgentSelectionStatus.TIMEOUT,
                        error="Agent execution timed out",
                        completion_timestamp=datetime.utcnow(),
                    )
                )
                if not continue_on_error:
                    break
            except Exception as e:
                logger.error(f"Error executing {agent_name}: {e}")
                results.append(
                    WizardAgentResult(
                        task_id=task_id,
                        agent_name=agent_name,
                        status=AgentSelectionStatus.FAILED,
                        error=str(e),
                        completion_timestamp=datetime.utcnow(),
                    )
                )
                if not continue_on_error:
                    break

        return results

    async def _execute_parallel(
        self,
        task_id: str,
        selected_agents: list[dict],
        task_description: str,
        task_context: dict[str, Any],
        timeout_seconds: float,
        fail_on_partial: bool,
    ) -> list[WizardAgentResult]:
        """Execute all agents concurrently, aggregate results."""
        tasks = [
            self._execute_agent_with_retry(
                task_id=task_id,
                agent_name=agent_info.get("name"),
                task_description=task_description,
                task_context=task_context,
                timeout_seconds=timeout_seconds,
            )
            for agent_info in selected_agents
        ]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=False),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Parallel execution timeout after {timeout_seconds}s")
            # Cancel remaining tasks
            for task in tasks:
                task.cancel()
            # Collect partial results
            results = []
            for task in tasks:
                try:
                    result = await asyncio.wait_for(task, timeout=1.0)
                    results.append(result)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

        return results

    async def _execute_agent_with_retry(
        self,
        task_id: str,
        agent_name: str,
        task_description: str,
        task_context: dict[str, Any],
        timeout_seconds: float,
    ) -> WizardAgentResult:
        """Execute an agent with automatic retry and fallback logic."""
        for attempt in range(MAX_RETRIES):
            try:
                agent = self.registry.get(agent_name)

                # Prepare execution context
                messages = [{"role": "user", "content": task_description}]

                # Call agent (simplified; actual implementation would use agent.arun_task)
                start_ms = asyncio.get_event_loop().time() * 1000
                output = await self._invoke_agent(
                    agent=agent,
                    messages=messages,
                    context=task_context,
                    timeout_seconds=timeout_seconds,
                )
                duration_ms = (asyncio.get_event_loop().time() * 1000) - start_ms

                # Log success
                self.metrics.track_request(
                    provider_name=agent_name,
                    tokens=0,  # Would be extracted from output
                    cost=0.0,  # Would be computed from model
                    response_time=duration_ms / 1000,
                    success=True,
                )

                return WizardAgentResult(
                    task_id=task_id,
                    agent_name=agent_name,
                    status=AgentSelectionStatus.COMPLETED,
                    output=output,
                    error=None,
                    metrics=ExecutionMetrics(
                        duration_ms=duration_ms,
                        tokens_used=0,
                        cost_usd=0.0,
                        provider_used=getattr(agent, "preferred_provider", None),
                    ),
                    completion_timestamp=datetime.utcnow(),
                )

            except asyncio.TimeoutError:
                logger.warning(
                    f"Agent {agent_name} attempt {attempt + 1}/{MAX_RETRIES} timed out"
                )
                if attempt < MAX_RETRIES - 1:
                    backoff = RETRY_BACKOFF_SECONDS[attempt]
                    await asyncio.sleep(backoff)
                    continue
                else:
                    return WizardAgentResult(
                        task_id=task_id,
                        agent_name=agent_name,
                        status=AgentSelectionStatus.TIMEOUT,
                        error=f"Timed out after {MAX_RETRIES} attempts",
                        completion_timestamp=datetime.utcnow(),
                    )

            except Exception as e:
                logger.warning(
                    f"Agent {agent_name} attempt {attempt + 1}/{MAX_RETRIES} failed: {e}"
                )
                self.metrics.track_request(
                    provider_name=agent_name,
                    tokens=0,
                    cost=0.0,
                    response_time=0,
                    success=False,
                )

                if attempt < MAX_RETRIES - 1:
                    backoff = RETRY_BACKOFF_SECONDS[attempt]
                    await asyncio.sleep(backoff)
                    continue
                else:
                    return WizardAgentResult(
                        task_id=task_id,
                        agent_name=agent_name,
                        status=AgentSelectionStatus.FAILED,
                        error=str(e),
                        completion_timestamp=datetime.utcnow(),
                    )

    async def _invoke_agent(
        self,
        agent,
        messages: list[dict],
        context: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Invoke an agent and return its output (simplified).

        In production, this would use agent.arun_task() or similar.
        """
        # Placeholder: simulate agent execution
        await asyncio.sleep(0.1)
        return {
            "status": "success",
            "message": f"Executed {agent.name}",
            "context_received": bool(context),
        }

    def _compute_overall_status(
        self, results: list[WizardAgentResult], fail_on_partial: bool
    ) -> WizardRunStatus:
        """Compute overall status from agent results."""
        if not results:
            return WizardRunStatus.FAILED

        completed_count = sum(1 for r in results if r.status == AgentSelectionStatus.COMPLETED)
        failed_count = sum(1 for r in results if r.status == AgentSelectionStatus.FAILED)
        timeout_count = sum(1 for r in results if r.status == AgentSelectionStatus.TIMEOUT)

        if completed_count == len(results):
            return WizardRunStatus.COMPLETED
        elif completed_count > 0 and not fail_on_partial:
            return WizardRunStatus.COMPLETED  # Partial success acceptable
        elif timeout_count > 0:
            return WizardRunStatus.TIMEOUT
        else:
            return WizardRunStatus.FAILED

    def _aggregate_analyses(
        self, results: list[WizardAgentResult], task_description: str
    ) -> Optional[AggregatedAnalysis]:
        """Aggregate analyses from multiple agent results."""
        if not results:
            return None

        raw_analyses = {}
        confidence_scores = []

        for result in results:
            if result.status == AgentSelectionStatus.COMPLETED and result.output:
                raw_analyses[result.agent_name] = result.output
                # Extract confidence if present in output
                if isinstance(result.output, dict):
                    confidence_scores.append(result.output.get("confidence", 0.5))

        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 0.5
        )

        return AggregatedAnalysis(
            summary=f"Completed analysis using {len(results)} agent(s)",
            confidence=avg_confidence,
            raw_analyses=raw_analyses,
        )

    @staticmethod
    def _extract_error_reason(
        results: list[WizardAgentResult], status: WizardRunStatus
    ) -> Optional[str]:
        """Extract first error reason from results if available."""
        if status == WizardRunStatus.COMPLETED:
            return None

        for result in results:
            if result.error:
                return result.error

        return None
