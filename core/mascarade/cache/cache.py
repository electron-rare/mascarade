"""Système de cache pour les réponses LLM."""

from __future__ import annotations

import time
import hashlib
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Entrée de cache avec métadonnées."""
    
    response: str
    tokens: int
    cost: float
    timestamp: float
    ttl: float
    strategy: str
    provider: str
    
    def is_expired(self) -> bool:
        """Vérifier si l'entrée de cache a expiré."""
        return time.time() > (self.timestamp + self.ttl)


class ResponseCache:
    """Cache en mémoire pour les réponses LLM."""
    
    def __init__(self, max_size: int = 1000) -> None:
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.hit_count = 0
        self.miss_count = 0
    
    def _generate_key(self, messages: list[dict], **kwargs) -> str:
        """Générer une clé de cache unique à partir des paramètres de requête."""
        
        messages_str = str(messages)
        kwargs_str = str(sorted(kwargs.items()))
        combined = f"{messages_str}|{kwargs_str}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def store(
        self,
        messages: list[dict],
        response: str,
        tokens: int,
        cost: float,
        ttl: float = 3600,
        **kwargs
    ) -> str:
        """Stocker une réponse dans le cache."""
        
        key = self._generate_key(messages, **kwargs)
        strategy = kwargs.get('strategy', 'best')
        provider = kwargs.get('provider', 'unknown')
        
        entry = CacheEntry(
            response=response,
            tokens=tokens,
            cost=cost,
            timestamp=time.time(),
            ttl=ttl,
            strategy=strategy,
            provider=provider
        )
        
        self.cache[key] = entry
        
        # Appliquer la limite de taille
        if len(self.cache) > self.max_size:
            self._evict_oldest()
        
        return key
    
    def retrieve(self, messages: list[dict], **kwargs) -> Optional[CacheEntry]:
        """Récupérer une réponse cache si disponible."""
        
        key = self._generate_key(messages, **kwargs)
        entry = self.cache.get(key)
        
        if entry and not entry.is_expired():
            self.hit_count += 1
            return entry
        
        self.miss_count += 1
        return None
    
    def _evict_oldest(self) -> None:
        """Supprimer l'entrée la plus ancienne pour faire de la place."""
        if not self.cache:
            return
        
        oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].timestamp)
        del self.cache[oldest_key]
    
    def get_stats(self) -> dict:
        """Obtenir les statistiques du cache."""
        
        hit_rate = (self.hit_count / (self.hit_count + self.miss_count)) * 100 \
                   if (self.hit_count + self.miss_count) > 0 else 0
        
        return {
            'entries': len(self.cache),
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': round(hit_rate, 2),
            'size_bytes': sum(len(entry.response) for entry in self.cache.values())
        }
    
    def clear(self) -> None:
        """Effacer toutes les entrées du cache."""
        self.cache = {}
        self.hit_count = 0
        self.miss_count = 0
