"""Registration module for AI Worker with GraphRuntime.

Provides convenience functions to register the AI Worker with the Universal Node Engine,
integrating Mascarade's Router, AgentRegistry, and Orchestrator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.agents.registry import AgentRegistry
    from mascarade.node_engine.runtime import GraphRuntime
    from mascarade.orchestrator.engine import Orchestrator
    from mascarade.router import Router

from mascarade.node_engine.workers.ai.worker import AIWorker

logger = logging.getLogger("mascarade.node_engine.workers.ai")


def register_ai_worker(
    runtime: GraphRuntime,
    router: Router | None = None,
    registry: AgentRegistry | None = None,
    orchestrator: Orchestrator | None = None,
) -> AIWorker:
    """Register AI Worker with GraphRuntime.

    Creates and registers an AIWorker instance with the provided GraphRuntime,
    enabling AI domain nodes (LLM inference, agent dispatch, orchestration).

    Args:
        runtime: GraphRuntime instance to register the worker with
        router: Optional Router instance. If None, creates a new Router.
        registry: Optional AgentRegistry instance. If None, creates a new AgentRegistry.
        orchestrator: Optional Orchestrator instance. If None, worker operates without orchestration support.

    Returns:
        AIWorker: The registered AIWorker instance

    Example:
        >>> from mascarade.node_engine.runtime import GraphRuntime
        >>> from mascarade.node_engine.workers.ai.register import register_ai_worker
        >>>
        >>> runtime = GraphRuntime()
        >>> ai_worker = register_ai_worker(runtime)
        >>>
        >>> # Runtime is now ready to execute AI domain nodes
        >>> workers = runtime.list_workers()
        >>> print(workers)
    """
    # Create default instances if not provided
    if router is None:
        from mascarade.router import Router

        router = Router()
        logger.debug("Created default Router for AI Worker")

    if registry is None:
        from mascarade.agents.registry import AgentRegistry

        registry = AgentRegistry()
        logger.debug("Created default AgentRegistry for AI Worker")

    # Create AI Worker instance
    ai_worker = AIWorker(
        router=router,
        registry=registry,
        orchestrator=orchestrator,
    )

    # Register with runtime
    runtime.register_worker(ai_worker)

    logger.info(
        "Registered AI Worker with GraphRuntime (router=%s, registry=%s, orchestrator=%s)",
        router.__class__.__name__,
        registry.__class__.__name__,
        orchestrator.__class__.__name__ if orchestrator else None,
    )

    return ai_worker
