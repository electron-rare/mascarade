"""Interface abstraite pour les workers Node."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from aiobreaker import CircuitBreaker

    from mascarade.node_engine.graph import ExecutionContext

logger = logging.getLogger("mascarade.node_engine")

# Exceptions transitoires communes pour workers
RETRYABLE_WORKER_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def make_worker_retry(*extra_exceptions: type[BaseException]):
    """Créer un décorateur retry avec exceptions spécifiques au worker."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_WORKER_EXCEPTIONS + tuple(extra_exceptions)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


@dataclass
class NodeCapability:
    """Declares what a worker can do — used for routing and scheduling."""

    node_types: list[str]
    domain: str
    supports_streaming: bool = False
    supports_cancellation: bool = True
    max_concurrent: int = 10
    requires_gpu: bool = False
    requires_hardware: bool = False
    estimated_memory_mb: int = 256
"""Abstract interface for Node Engine domain workers.

Each domain worker (AI, CAD, Electronics, Hardware) implements this interface
to provide graph-executable node types within their domain.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class NodeWorker(ABC):
    """
    Interface commune pour tous les workers Node.

    Circuit Breaker Support:
        Les méthodes execute() sont protégées par un circuit breaker
        pour prévenir les pannes en cascade. Le circuit breaker est automatiquement
        appliqué par le Node Engine lors des appels aux workers.

        États du circuit breaker:
        - CLOSED: Fonctionnement normal
        - OPEN: Échecs répétés, appels rejetés immédiatement
        - HALF_OPEN: Test de récupération

        Configuration par défaut: fail_max=5, timeout=60s
    Abstract interface for domain-specific node workers.

    Domain workers execute nodes within the graph runtime. Each worker is responsible
    for a specific domain (e.g., "ai", "cad", "electronics") and provides a set of
    node types that can be composed into graphs.

    Workers are registered with the GraphRuntime via the NodeWorkerRegistry.
    At execution time, the runtime dispatches node execution requests to the
    appropriate worker based on the node's domain.

    Attributes:
        name: Unique identifier for this worker (e.g., "ai-worker")
        domain: Domain this worker handles (e.g., "ai", "cad")

    Example:
        ```python
        class AIWorker(NodeWorker):
            name = "ai-worker"
            domain = "ai"

            async def execute(self, node_type, inputs, config, context):
                if node_type == "ai.llm-inference":
                    return await self._llm_inference(inputs, config)
                raise ValueError(f"Unknown node type: {node_type}")

            async def validate(self, node_type, inputs, config):
                errors = []
                if node_type == "ai.llm-inference" and "prompt" not in inputs:
                    errors.append("Missing required input: prompt")
                return errors

            def capabilities(self):
                return {
                    "node_types": ["ai.llm-inference", "ai.llm-stream"],
                    "domain": "ai",
                    "supports_streaming": True,
                    "max_concurrent": 10,
                }
        ```
    """

    name: str
    domain: str

    # Circuit breaker instance (set by Node Engine or CircuitBreakerManager)
    circuit_breaker: "CircuitBreaker | None" = None

    @abstractmethod
    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: "ExecutionContext",
    ) -> dict[str, Any]:
        """
        Exécuter un node avec les inputs fournis.

        Note: Cette méthode est protégée par un circuit breaker au niveau
        du Node Engine pour prévenir les pannes en cascade. Le circuit s'ouvre
        après 5 échecs consécutifs et rejette les appels pendant 60s avant
        de tester la récupération.

        Args:
            node_type: Identifiant du type de node
            inputs: Valeurs des ports d'entrée (par ID de port)
            config: Configuration spécifique au node
            context: Contexte d'exécution avec métadonnées et annulation

        Returns:
            Valeurs des ports de sortie (par ID de port)

        Raises:
            CircuitBreakerError: Si le circuit breaker est ouvert
            ConnectionError: Erreur de connexion
            TimeoutError: Timeout de l'exécution
            ValueError: Inputs ou configuration invalides
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute a node of the given type with provided inputs and configuration.

        This is the primary entry point for node execution. The runtime calls this
        method when a node of this worker's domain needs to be executed.

        Args:
            node_type: Fully qualified node type (e.g., "ai.llm-inference")
            inputs: Dictionary of input port values keyed by port name
            config: Node configuration parameters (e.g., temperature, model)
            context: Execution context for the current graph run

        Returns:
            Dictionary of output port values keyed by port name

        Raises:
            ValueError: If node_type is not supported by this worker
            RuntimeError: If execution fails due to worker-specific errors
            Any other exception that should propagate to the graph runtime
        """
        ...

    @abstractmethod
    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """
        Valider inputs et configuration avant exécution.

        Args:
            node_type: Identifiant du type de node
            inputs: Valeurs des ports d'entrée à valider
            config: Configuration spécifique au node à valider

        Returns:
            Liste des messages d'erreur de validation (vide si valide)

        Raises:
            ValueError: Erreur de validation avec détails
        Validate node inputs and configuration before execution.

        Called during graph validation to catch errors early. This allows
        validation errors to be reported before execution begins.

        Args:
            node_type: Fully qualified node type (e.g., "ai.agent-dispatch")
            inputs: Dictionary of input port values to validate
            config: Node configuration parameters to validate

        Returns:
            List of validation error messages. Empty list if validation passes.

        Example validation checks:
        - Required inputs are present
        - Input values are of expected types
        - Referenced resources exist (e.g., agent names in AgentRegistry)
        - Configuration values are within valid ranges
        """
        ...

    @abstractmethod
    def capabilities(self) -> NodeCapability:
        """Déclarer les capacités de ce worker."""
        ...

    @property
    def is_available(self) -> bool:
        """Vérifie si le worker est disponible pour exécution."""
        return True

    def on_init(self, context: "ExecutionContext") -> None:
        """
        Lifecycle hook: called when a graph execution starts.

        Optional override for workers that need to initialize resources,
        establish connections, or load models at the start of execution.

        Args:
            context: Execution context with graph/run metadata
        """
        pass

    def on_destroy(self, context: "ExecutionContext") -> None:
        """
        Lifecycle hook: called when a graph execution completes.

        Optional override for workers that need to release resources,
        close connections, or flush buffers at the end of execution.

        Args:
            context: Execution context with graph/run metadata
        """
        pass
    def capabilities(self) -> dict[str, Any]:
        """
        Declare worker capabilities for the registry.

        The runtime uses this information for scheduling, resource management,
        and feature discovery.

        Returns:
            Dictionary with capability metadata. Required keys:
            - node_types (list[str]): All node types this worker can execute
            - domain (str): Domain identifier (must match self.domain)

            Optional keys:
            - supports_streaming (bool): Whether worker supports streaming outputs
            - supports_cancellation (bool): Whether worker supports execution cancellation
            - max_concurrent (int): Maximum concurrent node executions
            - requires_gpu (bool): Whether worker requires GPU access
            - requires_hardware (bool): Whether worker requires hardware interface access
            - estimated_memory_mb (int): Estimated memory usage per execution

        Example:
            ```python
            {
                "node_types": ["ai.llm-inference", "ai.llm-stream"],
                "domain": "ai",
                "supports_streaming": True,
                "supports_cancellation": True,
                "max_concurrent": 10,
                "requires_gpu": False,
                "requires_hardware": False,
                "estimated_memory_mb": 128,
            }
            ```
        """
        ...

    @property
    def is_available(self) -> bool:
        """
        Check if the worker is available for execution.

        The runtime uses this to determine whether to include this worker
        in the active worker pool. Workers may be unavailable due to:
        - Missing API keys or credentials
        - Required services being offline
        - Hardware not connected

        Default implementation returns True. Override if your worker has
        specific availability requirements.

        Returns:
            True if worker is ready to execute nodes, False otherwise
        """
        return True
