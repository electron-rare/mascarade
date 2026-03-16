"""AI Worker implementation for the Universal Node Engine.

Wraps Mascarade Router and AgentRegistry to provide graph-executable AI nodes.
Implements the NodeWorker interface for AI domain operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.worker import NodeWorker

if TYPE_CHECKING:
    from mascarade.agents.registry import AgentRegistry
    from mascarade.router import Router

logger = logging.getLogger("mascarade.node_engine.workers.ai")


class AIWorker(NodeWorker):
    """
    AI domain worker for executing LLM inference, agent dispatch, and orchestration nodes.

    This worker integrates Mascarade's Router (multi-provider LLM routing) and
    AgentRegistry (agent definitions) into the Universal Node Engine. It provides
    node types for:
    - LLM inference (direct provider calls)
    - Agent dispatch (agent-based routing)
    - Orchestration (multi-step agent workflows)

    The worker follows the NodeWorker interface and is registered with the
    NodeWorkerRegistry at runtime initialization.

    Attributes:
        name: Unique identifier "ai-worker"
        domain: Domain identifier "ai"
        router: Mascarade Router instance for LLM provider access
        registry: AgentRegistry instance for agent definitions
    """

    name: str = "ai-worker"
    domain: str = "ai"

    def __init__(self, router: Router, registry: AgentRegistry) -> None:
        """
        Initialize AI worker with router and agent registry.

        Args:
            router: Mascarade Router instance for multi-provider LLM access
            registry: AgentRegistry instance for agent definitions and dispatch
        """
        self.router = router
        self.registry = registry
        logger.info(
            "AIWorker initialized with router=%s, registry=%s",
            router.__class__.__name__,
            registry.__class__.__name__,
        )

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute an AI domain node.

        Dispatches to the appropriate handler based on node_type:
        - ai.llm-inference: Direct LLM inference via Router
        - ai.agent-dispatch: Agent-based inference via AgentRegistry
        - ai.llm-stream: Streaming LLM inference (future)

        Args:
            node_type: Fully qualified node type (e.g., "ai.llm-inference")
            inputs: Dictionary of input port values (e.g., {"prompt": "..."})
            config: Node configuration (e.g., {"model": "gpt-4", "temperature": 0.7})
            context: Execution context for the current graph run

        Returns:
            Dictionary of output port values (e.g., {"response": LLMResponse(...)})

        Raises:
            ValueError: If node_type is not supported by this worker
            RuntimeError: If execution fails due to worker-specific errors
        """
        logger.debug("Executing node_type=%s with inputs=%s, config=%s", node_type, inputs, config)

        # Dispatch to node type handlers (to be implemented in future subtasks)
        if node_type == "ai.llm-inference":
            return await self._execute_llm_inference(inputs, config, context)
        elif node_type == "ai.agent-dispatch":
            return await self._execute_agent_dispatch(inputs, config, context)
        elif node_type == "ai.llm-stream":
            return await self._execute_llm_stream(inputs, config, context)
        else:
            raise ValueError(f"Unsupported node type: {node_type}")

    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """
        Validate node inputs and configuration before execution.

        Performs domain-specific validation checks:
        - Required inputs are present
        - Agent names exist in AgentRegistry (for agent-dispatch nodes)
        - Configuration values are within valid ranges
        - Referenced resources are available

        Args:
            node_type: Fully qualified node type (e.g., "ai.agent-dispatch")
            inputs: Dictionary of input port values to validate
            config: Node configuration parameters to validate

        Returns:
            List of validation error messages. Empty list if validation passes.
        """
        errors: list[str] = []

        # Dispatch to node type validators (to be implemented in future subtasks)
        if node_type == "ai.llm-inference":
            errors.extend(self._validate_llm_inference(inputs, config))
        elif node_type == "ai.agent-dispatch":
            errors.extend(self._validate_agent_dispatch(inputs, config))
        elif node_type == "ai.llm-stream":
            errors.extend(self._validate_llm_stream(inputs, config))
        else:
            errors.append(f"Unsupported node type: {node_type}")

        return errors

    def capabilities(self) -> dict[str, Any]:
        """
        Declare AI worker capabilities for the registry.

        Returns:
            Dictionary with capability metadata including:
            - node_types: List of supported node types
            - domain: Domain identifier "ai"
            - supports_streaming: Whether streaming is supported
            - max_concurrent: Maximum concurrent executions
        """
        return {
            "node_types": [
                "ai.llm-inference",
                "ai.agent-dispatch",
                "ai.llm-stream",
            ],
            "domain": "ai",
            "supports_streaming": True,
            "supports_cancellation": False,  # Future implementation
            "max_concurrent": 10,
            "requires_gpu": False,
            "requires_hardware": False,
            "estimated_memory_mb": 128,
        }

    @property
    def is_available(self) -> bool:
        """
        Check if the AI worker is available for execution.

        The worker is available if the Router has at least one configured provider.
        Workers may be unavailable due to missing API keys or provider configuration.

        Returns:
            True if at least one LLM provider is configured, False otherwise
        """
        # Check if router has any configured providers
        # For now, return True as a skeleton — actual provider check will be
        # implemented when Router integration is complete
        return True

    # Private helper methods (to be implemented in future subtasks)

    async def _execute_llm_inference(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Execute ai.llm-inference node (stub for future implementation)."""
        raise NotImplementedError("ai.llm-inference execution not yet implemented")

    async def _execute_agent_dispatch(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Execute ai.agent-dispatch node (stub for future implementation)."""
        raise NotImplementedError("ai.agent-dispatch execution not yet implemented")

    async def _execute_llm_stream(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """Execute ai.llm-stream node (stub for future implementation)."""
        raise NotImplementedError("ai.llm-stream execution not yet implemented")

    def _validate_llm_inference(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.llm-inference node (stub for future implementation)."""
        return []

    def _validate_agent_dispatch(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.agent-dispatch node (stub for future implementation)."""
        return []

    def _validate_llm_stream(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.llm-stream node (stub for future implementation)."""
        return []
