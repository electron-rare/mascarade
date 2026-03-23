"""Gestionnaire de circuit breakers pour prévenir les pannes en cascade."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ParamSpec, TypeVar

from aiobreaker import CircuitBreaker, CircuitBreakerListener, CircuitBreakerState

logger = logging.getLogger("mascarade.resilience")

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(StrEnum):
    """États possibles d'un circuit breaker."""

    CLOSED = "closed"  # Fonctionnement normal
    OPEN = "open"  # Circuit ouvert, rejette immédiatement les appels
    HALF_OPEN = "half_open"  # Test de récupération


@dataclass
class CircuitBreakerMetrics:
    """Métriques d'un circuit breaker."""

    name: str
    state: CircuitState
    fail_count: int = 0
    success_count: int = 0
    last_failure: float | None = None
    last_success: float | None = None
    opened_at: float | None = None


class LoggingListener(CircuitBreakerListener):
    """Listener pour logger les transitions d'état du circuit breaker."""

    def __init__(self, name: str) -> None:
        self.name = name

    def state_change(
        self, cb: CircuitBreaker, old_state: CircuitBreakerState, new_state: CircuitBreakerState
    ) -> None:
        """Log les changements d'état."""
        logger.warning(
            f"Circuit breaker '{self.name}' transition: {old_state.name} -> {new_state.name}"
        )

    def failure(self, cb: CircuitBreaker, exc: BaseException) -> None:
        """Log les échecs."""
        logger.debug(f"Circuit breaker '{self.name}' recorded failure: {exc.__class__.__name__}")

    def success(self, cb: CircuitBreaker) -> None:
        """Log les succès."""
        logger.debug(f"Circuit breaker '{self.name}' recorded success")


class CircuitBreakerManager:
    """
    Gestionnaire centralisé de circuit breakers pour tous les services externes.

    Utilise aiobreaker pour implémenter le pattern Circuit Breaker et prévenir
    les pannes en cascade lors de défaillances de services externes (LLM providers,
    Redis, MCP tools, etc.).

    Configuration par défaut:
    - fail_max: 5 échecs consécutifs déclenchent l'état OPEN
    - timeout_duration: 60s avant la transition vers HALF_OPEN
    - excluded_exceptions: ValidationError, ValueError (non transitoires)

    États:
    - CLOSED: Fonctionnement normal, tous les appels passent
    - OPEN: Circuit ouvert, tous les appels échouent immédiatement
    - HALF_OPEN: Test de récupération, un appel de test passe

    Usage:
        manager = CircuitBreakerManager()
        cb = manager.get_breaker("openai-provider")

        @cb
        async def call_openai():
            return await client.send(...)

        result = await call_openai()
    """

    def __init__(
        self,
        fail_max: int = 5,
        timeout_duration: int = 60,
        excluded_exceptions: tuple[type[BaseException], ...] = (ValueError, TypeError),
    ) -> None:
        """
        Initialise le gestionnaire de circuit breakers.

        Args:
            fail_max: Nombre d'échecs consécutifs avant ouverture du circuit
            timeout_duration: Durée en secondes avant tentative de récupération
            excluded_exceptions: Exceptions qui ne déclenchent pas le circuit breaker
        """
        self._breakers: dict[str, CircuitBreaker] = {}
        self._fail_max = fail_max
        self._timeout_duration = timeout_duration
        self._excluded_exceptions = excluded_exceptions
        logger.info(
            f"CircuitBreakerManager initialized: fail_max={fail_max}, "
            f"timeout={timeout_duration}s"
        )

    def get_breaker(self, name: str) -> CircuitBreaker:
        """
        Récupère ou crée un circuit breaker pour un service nommé.

        Args:
            name: Nom unique du service (ex: "openai-provider", "redis-cache")

        Returns:
            Instance de CircuitBreaker configurée
        """
        if name not in self._breakers:
            breaker = CircuitBreaker(
                fail_max=self._fail_max,
                timeout_duration=self._timeout_duration,
                exclude=self._excluded_exceptions,
                name=name,
            )
            # Ajoute le listener pour le logging
            breaker.add_listener(LoggingListener(name))
            self._breakers[name] = breaker
            logger.info(f"Created circuit breaker: {name}")

        return self._breakers[name]

    def get_metrics(self, name: str) -> CircuitBreakerMetrics:
        """
        Récupère les métriques d'un circuit breaker.

        Args:
            name: Nom du circuit breaker

        Returns:
            Métriques du circuit breaker

        Raises:
            KeyError: Si le circuit breaker n'existe pas
        """
        if name not in self._breakers:
            raise KeyError(f"Circuit breaker '{name}' not found")

        breaker = self._breakers[name]
        state_map = {
            CircuitBreakerState.STATE_CLOSED: CircuitState.CLOSED,
            CircuitBreakerState.STATE_OPEN: CircuitState.OPEN,
            CircuitBreakerState.STATE_HALF_OPEN: CircuitState.HALF_OPEN,
        }

        return CircuitBreakerMetrics(
            name=name,
            state=state_map.get(breaker.current_state, CircuitState.CLOSED),
            fail_count=breaker.fail_counter,
            # aiobreaker ne track pas success_count, utiliser 0 par défaut
            success_count=0,
        )

    def get_all_metrics(self) -> list[CircuitBreakerMetrics]:
        """
        Récupère les métriques de tous les circuit breakers.

        Returns:
            Liste des métriques de tous les circuit breakers
        """
        return [self.get_metrics(name) for name in self._breakers.keys()]

    def reset(self, name: str) -> None:
        """
        Réinitialise un circuit breaker à l'état CLOSED.

        Args:
            name: Nom du circuit breaker

        Raises:
            KeyError: Si le circuit breaker n'existe pas
        """
        if name not in self._breakers:
            raise KeyError(f"Circuit breaker '{name}' not found")

        breaker = self._breakers[name]
        breaker.close()
        logger.info(f"Circuit breaker '{name}' manually reset to CLOSED")

    def reset_all(self) -> None:
        """Réinitialise tous les circuit breakers à l'état CLOSED."""
        for name, breaker in self._breakers.items():
            breaker.close()
            logger.info(f"Circuit breaker '{name}' reset to CLOSED")

    @property
    def is_healthy(self) -> bool:
        """
        Vérifie si tous les circuit breakers sont en état CLOSED.

        Returns:
            True si tous les breakers sont fermés, False sinon
        """
        return all(
            breaker.current_state == CircuitBreakerState.STATE_CLOSED
            for breaker in self._breakers.values()
        )

    def get_health_summary(self) -> dict[str, Any]:
        """
        Résumé de santé de tous les circuit breakers.

        Returns:
            Dict avec statut global et détails par breaker
        """
        metrics = self.get_all_metrics()
        open_count = sum(1 for m in metrics if m.state == CircuitState.OPEN)
        half_open_count = sum(1 for m in metrics if m.state == CircuitState.HALF_OPEN)

        return {
            "healthy": self.is_healthy,
            "total_breakers": len(metrics),
            "open": open_count,
            "half_open": half_open_count,
            "closed": len(metrics) - open_count - half_open_count,
            "breakers": [
                {
                    "name": m.name,
                    "state": m.state.value,
                    "fail_count": m.fail_count,
                }
                for m in metrics
            ],
        }
