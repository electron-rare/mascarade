"""Mécanisme de fallback pour le routeur LLM."""

from __future__ import annotations

from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class FallbackState:
    """État du mécanisme de fallback."""
    
    max_attempts: int = 3
    failed_attempts: dict[str, int] = None
    
    def __post_init__(self) -> None:
        self.failed_attempts = {}
    
    def build_sequence(
        self,
        strategy: str,
        provider: str | None,
        available_providers: List[str]
    ) -> List[Tuple[str, str | None]]:
        """Construire la séquence de fallback."""
        
        sequence: List[Tuple[str, str | None]] = []
        
        # Premier essai : la requête originale
        if provider:
            sequence.append((strategy, provider))
        else:
            sequence.append((strategy, None))
        
        # Essais supplémentaires : essayer d'autres stratégies
        fallback_strategies = ['best', 'cheapest', 'fastest']
        for fallback_strategy in fallback_strategies:
            if fallback_strategy != strategy:
                sequence.append((fallback_strategy, None))
        
        # Dernier essai : essayer des providers spécifiques
        for available_provider in available_providers:
            if not provider or available_provider != provider:
                sequence.append((strategy, available_provider))
        
        # Limiter au nombre maximum d'essais
        return sequence[:self.max_attempts]
    
    def record_failure(self, provider_name: str) -> None:
        """Enregistrer un échec pour un provider."""
        self.failed_attempts[provider_name] = self.failed_attempts.get(provider_name, 0) + 1
    
    def get_failure_stats(self) -> dict:
        """Obtenir les statistiques des échecs."""
        return {
            'failed_attempts': dict(self.failed_attempts),
            'total_failures': sum(self.failed_attempts.values())
        }
    
    def reset(self) -> None:
        """Réinitialiser les statistiques des échecs."""
        self.failed_attempts = {}
