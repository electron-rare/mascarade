"""Circuit breaker pattern pour la gestion des défaillances."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CircuitState(Enum):
    """États du circuit breaker."""

    CLOSED = "closed"  # Fonctionnement normal
    OPEN = "open"  # Circuit ouvert, rejette les requêtes
    HALF_OPEN = "half_open"  # Test de récupération


@dataclass
class CircuitBreaker:
    """Circuit breaker avec suivi des échecs dans une fenêtre temporelle."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # secondes
    window_size: float = 120.0  # secondes
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_times: list[float] = field(default_factory=list, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Obtenir l'état actuel du circuit."""
        return self._state

    def _clean_old_failures(self) -> None:
        """Nettoyer les échecs en dehors de la fenêtre temporelle."""
        current_time = time.time()
        cutoff_time = current_time - self.window_size
        self._failure_times = [t for t in self._failure_times if t > cutoff_time]

    def _get_failure_count(self) -> int:
        """Obtenir le nombre d'échecs dans la fenêtre temporelle."""
        self._clean_old_failures()
        return len(self._failure_times)

    def can_execute(self) -> bool:
        """Vérifier si une requête peut être exécutée."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Vérifier si le timeout de récupération est écoulé
            if (
                self._last_failure_time
                and time.time() - self._last_failure_time >= self.recovery_timeout
            ):
                self._transition_to_half_open()
                return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            # Limiter le nombre d'appels en mode half-open
            return self._half_open_calls < self.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Enregistrer un succès."""
        if self._state == CircuitState.HALF_OPEN:
            self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            # En mode closed, un succès peut aider à nettoyer les vieux échecs
            self._clean_old_failures()

    def record_failure(self) -> None:
        """Enregistrer un échec."""
        current_time = time.time()
        self._failure_times.append(current_time)
        self._last_failure_time = current_time

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            if self._get_failure_count() >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition vers l'état OPEN."""
        self._state = CircuitState.OPEN
        self._half_open_calls = 0

    def _transition_to_half_open(self) -> None:
        """Transition vers l'état HALF_OPEN."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0

    def _transition_to_closed(self) -> None:
        """Transition vers l'état CLOSED."""
        self._state = CircuitState.CLOSED
        self._failure_times = []
        self._half_open_calls = 0

    def get_stats(self) -> dict:
        """Obtenir les statistiques du circuit breaker."""
        return {
            "state": self._state.value,
            "failure_count": self._get_failure_count(),
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self._last_failure_time,
            "half_open_calls": self._half_open_calls,
        }

    def reset(self) -> None:
        """Réinitialiser le circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_times = []
        self._last_failure_time = None
        self._half_open_calls = 0
