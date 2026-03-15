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
class ProviderCircuitState:
    """État du circuit breaker pour un provider individuel."""

    state: CircuitState = CircuitState.CLOSED
    failure_times: list[float] = field(default_factory=list)
    last_failure_time: float | None = None
    half_open_calls: int = 0


@dataclass
class CircuitBreaker:
    """Circuit breaker avec suivi des échecs par provider dans une fenêtre temporelle."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # secondes
    window_size: float = 120.0  # secondes
    half_open_max_calls: int = 3

    # Per-provider circuit states
    _provider_states: dict[str, ProviderCircuitState] = field(default_factory=dict, init=False)

    # Legacy global state (deprecated, kept for backward compatibility)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_times: list[float] = field(default_factory=list, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Obtenir l'état actuel du circuit (legacy global state)."""
        return self._state

    def _get_provider_state(self, provider_name: str) -> ProviderCircuitState:
        """Obtenir ou créer l'état du circuit pour un provider."""
        if provider_name not in self._provider_states:
            self._provider_states[provider_name] = ProviderCircuitState()
        return self._provider_states[provider_name]

    def get_state(self, provider_name: str) -> CircuitState:
        """Obtenir l'état du circuit pour un provider spécifique."""
        return self._get_provider_state(provider_name).state

    def is_open(self, provider_name: str) -> bool:
        """Vérifier si le circuit est ouvert pour un provider."""
        return self.get_state(provider_name) == CircuitState.OPEN

    def _clean_old_failures(self, provider_name: str | None = None) -> None:
        """Nettoyer les échecs en dehors de la fenêtre temporelle."""
        current_time = time.time()
        cutoff_time = current_time - self.window_size

        if provider_name:
            # Per-provider cleanup
            pstate = self._get_provider_state(provider_name)
            pstate.failure_times = [t for t in pstate.failure_times if t > cutoff_time]
        else:
            # Legacy global cleanup
            self._failure_times = [t for t in self._failure_times if t > cutoff_time]

    def _get_failure_count(self, provider_name: str | None = None) -> int:
        """Obtenir le nombre d'échecs dans la fenêtre temporelle."""
        self._clean_old_failures(provider_name)
        if provider_name:
            return len(self._get_provider_state(provider_name).failure_times)
        return len(self._failure_times)

    def can_execute(self, provider_name: str | None = None) -> bool:
        """Vérifier si une requête peut être exécutée."""
        if provider_name:
            # Per-provider check
            pstate = self._get_provider_state(provider_name)
            if pstate.state == CircuitState.CLOSED:
                return True

            if pstate.state == CircuitState.OPEN:
                # Vérifier si le timeout de récupération est écoulé
                if (
                    pstate.last_failure_time
                    and time.time() - pstate.last_failure_time >= self.recovery_timeout
                ):
                    self._transition_to_half_open(provider_name)
                    return True
                return False

            if pstate.state == CircuitState.HALF_OPEN:
                # Limiter le nombre d'appels en mode half-open
                return pstate.half_open_calls < self.half_open_max_calls

            return False

        # Legacy global check
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

    def record_success(self, provider_name: str | None = None) -> None:
        """Enregistrer un succès."""
        if provider_name:
            # Per-provider success
            pstate = self._get_provider_state(provider_name)
            if pstate.state == CircuitState.HALF_OPEN:
                self._transition_to_closed(provider_name)
            elif pstate.state == CircuitState.CLOSED:
                # En mode closed, un succès peut aider à nettoyer les vieux échecs
                self._clean_old_failures(provider_name)
        else:
            # Legacy global success
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # En mode closed, un succès peut aider à nettoyer les vieux échecs
                self._clean_old_failures()

    def record_failure(self, provider_name: str | None = None) -> None:
        """Enregistrer un échec."""
        current_time = time.time()

        if provider_name:
            # Per-provider failure
            pstate = self._get_provider_state(provider_name)
            pstate.failure_times.append(current_time)
            pstate.last_failure_time = current_time

            if pstate.state == CircuitState.HALF_OPEN:
                self._transition_to_open(provider_name)
            elif pstate.state == CircuitState.CLOSED:
                if self._get_failure_count(provider_name) >= self.failure_threshold:
                    self._transition_to_open(provider_name)
        else:
            # Legacy global failure
            self._failure_times.append(current_time)
            self._last_failure_time = current_time

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                if self._get_failure_count() >= self.failure_threshold:
                    self._transition_to_open()

    def _transition_to_open(self, provider_name: str | None = None) -> None:
        """Transition vers l'état OPEN."""
        if provider_name:
            pstate = self._get_provider_state(provider_name)
            pstate.state = CircuitState.OPEN
            pstate.half_open_calls = 0
        else:
            self._state = CircuitState.OPEN
            self._half_open_calls = 0

    def _transition_to_half_open(self, provider_name: str | None = None) -> None:
        """Transition vers l'état HALF_OPEN."""
        if provider_name:
            pstate = self._get_provider_state(provider_name)
            pstate.state = CircuitState.HALF_OPEN
            pstate.half_open_calls = 0
        else:
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    def _transition_to_closed(self, provider_name: str | None = None) -> None:
        """Transition vers l'état CLOSED."""
        if provider_name:
            pstate = self._get_provider_state(provider_name)
            pstate.state = CircuitState.CLOSED
            pstate.failure_times = []
            pstate.half_open_calls = 0
        else:
            self._state = CircuitState.CLOSED
            self._failure_times = []
            self._half_open_calls = 0

    def get_stats(self, provider_name: str | None = None) -> dict:
        """Obtenir les statistiques du circuit breaker."""
        if provider_name:
            # Per-provider stats
            pstate = self._get_provider_state(provider_name)
            return {
                "provider": provider_name,
                "state": pstate.state.value,
                "failure_count": self._get_failure_count(provider_name),
                "failure_threshold": self.failure_threshold,
                "last_failure_time": pstate.last_failure_time,
                "half_open_calls": pstate.half_open_calls,
            }

        # Global stats (all providers)
        provider_stats = {
            name: {
                "state": pstate.state.value,
                "failure_count": self._get_failure_count(name),
                "failure_threshold": self.failure_threshold,
                "last_failure_time": pstate.last_failure_time,
                "half_open_calls": pstate.half_open_calls,
            }
            for name, pstate in self._provider_states.items()
        }

        return {
            "legacy_state": self._state.value,
            "legacy_failure_count": self._get_failure_count(),
            "providers": provider_stats,
        }

    def reset(self, provider_name: str | None = None) -> None:
        """Réinitialiser le circuit breaker."""
        if provider_name:
            # Reset specific provider
            if provider_name in self._provider_states:
                del self._provider_states[provider_name]
        else:
            # Reset everything
            self._state = CircuitState.CLOSED
            self._failure_times = []
            self._last_failure_time = None
            self._half_open_calls = 0
            self._provider_states.clear()
