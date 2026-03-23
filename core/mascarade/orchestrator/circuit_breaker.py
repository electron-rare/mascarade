"""Circuit breaker pour gérer les défaillances d'agents."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class CircuitState(StrEnum):
    """État du circuit breaker."""

    CLOSED = "closed"  # Fonctionnement normal
    OPEN = "open"  # Circuit ouvert, requêtes bloquées
    HALF_OPEN = "half_open"  # Test de récupération


@dataclass
class CircuitBreaker:
    """Circuit breaker pour surveiller et gérer les défaillances d'agents."""

    failure_threshold: int = 5  # Nombre d'échecs avant d'ouvrir le circuit
    success_threshold: int = 2  # Nombre de succès en half-open avant de fermer
    timeout: float = 60.0  # Délai avant de passer de OPEN à HALF_OPEN (secondes)

    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: float | None = field(default=None, init=False)
    last_state_change: float = field(default_factory=time.time, init=False)
    on_state_change: Callable[[CircuitState, CircuitState], None] | None = field(
        default=None, init=False, repr=False
    )

    def record_success(self) -> None:
        """Enregistrer un succès d'exécution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Réinitialiser le compteur d'échecs sur un succès
            self.failure_count = 0

    def record_failure(self) -> None:
        """Enregistrer un échec d'exécution."""
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Un échec en half-open rouvre immédiatement le circuit
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()

    def can_execute(self) -> bool:
        """Vérifier si une exécution est autorisée."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Vérifier si le timeout est écoulé pour passer en half-open
            if (
                self.last_failure_time
                and (time.time() - self.last_failure_time) >= self.timeout
            ):
                self._transition_to_half_open()
                return True
            return False

        # HALF_OPEN : autoriser une tentative de test
        return True

    def _transition_to_open(self) -> None:
        """Transition vers l'état OPEN."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        self.success_count = 0
        if self.on_state_change and old_state != CircuitState.OPEN:
            self.on_state_change(old_state, CircuitState.OPEN)

    def _transition_to_half_open(self) -> None:
        """Transition vers l'état HALF_OPEN."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = time.time()
        self.success_count = 0
        self.failure_count = 0
        if self.on_state_change and old_state != CircuitState.HALF_OPEN:
            self.on_state_change(old_state, CircuitState.HALF_OPEN)

    def _transition_to_closed(self) -> None:
        """Transition vers l'état CLOSED."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()
        self.failure_count = 0
        self.success_count = 0
        if self.on_state_change and old_state != CircuitState.CLOSED:
            self.on_state_change(old_state, CircuitState.CLOSED)

    def get_stats(self) -> dict:
        """Obtenir les statistiques du circuit breaker."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "last_failure_time": self.last_failure_time,
            "time_since_last_change": time.time() - self.last_state_change,
        }

    def reset(self) -> None:
        """Réinitialiser le circuit breaker à l'état CLOSED."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()
