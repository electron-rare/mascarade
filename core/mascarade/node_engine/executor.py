"""Node Executor — exécution et validation de nœuds individuels."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from mascarade.node_engine.types import NodeType, PortType

logger = logging.getLogger("mascarade.node_engine")


@dataclass
class NodeExecutionResult:
    """Résultat de l'exécution d'un nœud."""

    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class NodeExecutor:
    """Exécuteur de nœuds avec validation et gestion des timeouts."""

    timeout_default_s: int = 120

    async def execute(
        self,
        node_type: NodeType,
        inputs: dict[str, Any],
        *,
        timeout_s: int | None = None,
    ) -> NodeExecutionResult:
        """Exécuter un nœud avec validation des entrées/sorties et gestion du timeout.

        Args:
            node_type: Définition du type de nœud à exécuter
            inputs: Valeurs d'entrée pour le nœud
            timeout_s: Timeout personnalisé en secondes (optionnel)

        Returns:
            NodeExecutionResult avec les sorties ou l'erreur
        """
        timeout = timeout_s if timeout_s is not None else self.timeout_default_s

        # Valider les entrées
        validation_error = self._validate_inputs(node_type, inputs)
        if validation_error:
            return NodeExecutionResult(
                success=False,
                error=validation_error,
            )

        # Exécuter avec timeout
        try:
            import time

            start_time = time.time()

            # L'exécution réelle sera déléguée au worker
            # Pour l'instant, on retourne un placeholder
            outputs = await asyncio.wait_for(
                self._execute_node(node_type, inputs),
                timeout=timeout,
            )

            execution_time_ms = (time.time() - start_time) * 1000

            # Valider les sorties
            validation_error = self._validate_outputs(node_type, outputs)
            if validation_error:
                return NodeExecutionResult(
                    success=False,
                    error=validation_error,
                    execution_time_ms=execution_time_ms,
                )

            return NodeExecutionResult(
                success=True,
                outputs=outputs,
                execution_time_ms=execution_time_ms,
            )

        except asyncio.TimeoutError:
            return NodeExecutionResult(
                success=False,
                error=f"Node execution timed out after {timeout}s",
            )
        except Exception as exc:
            logger.exception("Node execution failed: %s", exc)
            return NodeExecutionResult(
                success=False,
                error=f"Execution error: {exc!s}",
            )

    async def _execute_node(
        self, node_type: NodeType, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Exécuter le nœud (à implémenter par les workers).

        Cette méthode sera override par les workers spécifiques ou déléguée
        via un registry de workers.

        Args:
            node_type: Type de nœud à exécuter
            inputs: Entrées validées

        Returns:
            Sorties du nœud
        """
        # Placeholder pour l'instant - sera implémenté lors de l'intégration avec les workers
        raise NotImplementedError(
            f"Node execution not implemented for {node_type.id}"
        )

    def _validate_inputs(
        self, node_type: NodeType, inputs: dict[str, Any]
    ) -> str | None:
        """Valider les entrées du nœud.

        Args:
            node_type: Type de nœud
            inputs: Entrées à valider

        Returns:
            Message d'erreur si invalide, None sinon
        """
        # Vérifier les entrées requises
        for port in node_type.inputs:
            if port.required and port.name not in inputs:
                return f"Missing required input: {port.name}"

        # Vérifier les entrées inattendues
        valid_input_names = {port.name for port in node_type.inputs}
        for input_name in inputs:
            if input_name not in valid_input_names:
                return f"Unexpected input: {input_name}"

        return None

    def _validate_outputs(
        self, node_type: NodeType, outputs: dict[str, Any]
    ) -> str | None:
        """Valider les sorties du nœud.

        Args:
            node_type: Type de nœud
            outputs: Sorties à valider

        Returns:
            Message d'erreur si invalide, None sinon
        """
        # Vérifier les sorties requises
        for port in node_type.outputs:
            if port.required and port.name not in outputs:
                return f"Missing required output: {port.name}"

        return None

    def build_execution_context(
        self,
        node_type: NodeType,
        inputs: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Construire le contexte d'exécution pour un nœud.

        Args:
            node_type: Type de nœud
            inputs: Entrées du nœud
            metadata: Métadonnées additionnelles (optionnel)

        Returns:
            Contexte d'exécution structuré
        """
        return {
            "node_id": node_type.id,
            "category": node_type.category,
            "inputs": inputs,
            "metadata": metadata or {},
        }
