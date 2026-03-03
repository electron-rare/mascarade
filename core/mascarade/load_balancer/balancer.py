"""Système de load balancing pour les providers LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import random
from collections import deque


@dataclass
class ProviderStats:
    """Statistiques en temps réel pour un provider."""
    
    name: str
    current_load: int = 0
    pending_requests: int = 0
    last_used: float = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0
    
    def avg_response_time(self) -> float:
        """Calculer le temps de réponse moyen."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def error_rate(self) -> float:
        """Calculer le taux d'erreur."""
        total = self.current_load + self.pending_requests
        return self.error_count / total if total > 0 else 0.0


class LoadBalancer:
    """Load balancer intelligent pour les providers LLM."""
    
    def __init__(self) -> None:
        self.providers: Dict[str, ProviderStats] = {}
        self.request_queue: Dict[str, deque] = {}
        self.last_update = time.time()
    
    def register_provider(self, provider_name: str) -> None:
        """Enregistrer un nouveau provider."""
        if provider_name not in self.providers:
            self.providers[provider_name] = ProviderStats(provider_name)
            self.request_queue[provider_name] = deque()
    
    def select_provider(
        self,
        available_providers: List[str],
        strategy: str = 'round_robin'
    ) -> Optional[str]:
        """Sélectionner le meilleur provider basé sur la stratégie de load balancing."""
        
        if not available_providers:
            return None
        
        # Filtrer les providers enregistrés
        candidates = [p for p in available_providers if p in self.providers]
        
        if not candidates:
            return random.choice(available_providers)
        
        if strategy == 'round_robin':
            return self._round_robin(candidates)
        elif strategy == 'least_connections':
            return self._least_connections(candidates)
        elif strategy == 'fastest_response':
            return self._fastest_response(candidates)
        elif strategy == 'least_errors':
            return self._least_errors(candidates)
        elif strategy == 'weighted':
            return self._weighted_random(candidates)
        else:
            return random.choice(candidates)
    
    def _round_robin(self, candidates: List[str]) -> str:
        """Sélection round robin."""
        return min(candidates, key=lambda p: self.providers[p].last_used)
    
    def _least_connections(self, candidates: List[str]) -> str:
        """Sélectionner le provider avec le moins de connexions actives."""
        return min(candidates, key=lambda p: self.providers[p].current_load)
    
    def _fastest_response(self, candidates: List[str]) -> str:
        """Sélectionner le provider avec le temps de réponse moyen le plus rapide."""
        return min(candidates, key=lambda p: self.providers[p].avg_response_time())
    
    def _least_errors(self, candidates: List[str]) -> str:
        """Sélectionner le provider avec le taux d'erreur le plus bas."""
        return min(candidates, key=lambda p: self.providers[p].error_rate())
    
    def _weighted_random(self, candidates: List[str]) -> str:
        """Sélection aléatoire pondérée basée sur la performance."""
        
        weights = []
        total_weight = 0
        
        for provider in candidates:
            stats = self.providers[provider]
            
            # Poids basé sur la charge, le temps de réponse et le taux d'erreur
            load_factor = 1.0 / (stats.current_load + 1)
            time_factor = 1.0 / (stats.avg_response_time() + 0.1)
            error_factor = 1.0 - stats.error_rate()
            
            weight = load_factor * time_factor * error_factor
            weights.append(weight)
            total_weight += weight
        
        # Normaliser les poids
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        
        # Sélection aléatoire pondérée
        rand = random.random()
        cumulative = 0
        for i, weight in enumerate(weights):
            cumulative += weight
            if rand <= cumulative:
                return candidates[i]
        
        return candidates[-1]
    
    def request_started(self, provider_name: str) -> None:
        """Notifier le balancer qu'une requête a commencé."""
        if provider_name in self.providers:
            self.providers[provider_name].pending_requests += 1
            self.providers[provider_name].last_used = time.time()
    
    def request_completed(
        self,
        provider_name: str,
        response_time: float,
        success: bool
    ) -> None:
        """Notifier le balancer qu'une requête est terminée."""
        if provider_name in self.providers:
            stats = self.providers[provider_name]
            stats.pending_requests = max(0, stats.pending_requests - 1)
            stats.current_load = max(0, stats.current_load - 1)
            stats.response_times.append(response_time)
            
            if not success:
                stats.error_count += 1
    
    def get_load_stats(self) -> dict:
        """Obtenir les statistiques actuelles de load balancing."""
        
        return {
            'providers': {
                name: {
                    'current_load': stats.current_load,
                    'pending_requests': stats.pending_requests,
                    'avg_response_time': stats.avg_response_time(),
                    'error_rate': stats.error_rate(),
                    'last_used': stats.last_used
                }
                for name, stats in self.providers.items()
            },
            'total_requests': sum(stats.current_load for stats in self.providers.values()),
            'total_pending': sum(stats.pending_requests for stats in self.providers.values())
        }
    
    def reset_stats(self) -> None:
        """Réinitialiser toutes les statistiques de load balancing."""
        for stats in self.providers.values():
            stats.current_load = 0
            stats.pending_requests = 0
            stats.response_times.clear()
            stats.error_count = 0
