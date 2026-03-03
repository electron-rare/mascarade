# Caching System

## Overview
Intelligent caching system for LLM responses to improve performance and reduce costs.

## Core Cache System

### File: `core/mascarade/cache/cache.py`
```python
import time
import hashlib
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class CacheEntry:
    """Cached LLM response with metadata"""
    response: str
    tokens: int
    cost: float
    timestamp: float
    ttl: float  # Time to live in seconds
    strategy: str
    provider: str
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() > (self.timestamp + self.ttl)

class ResponseCache:
    """In-memory cache for LLM responses"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.hit_count = 0
        self.miss_count = 0
    
    def _generate_key(self, messages: list[dict], **kwargs) -> str:
        """Generate unique cache key from request parameters"""
        
        # Convert messages to string representation
        messages_str = str(messages)
        
        # Include relevant kwargs in key
        kwargs_str = str(sorted(kwargs.items()))
        
        # Create hash
        combined = f"{messages_str}|{kwargs_str}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def store(
        self,
        messages: list[dict],
        response: str,
        tokens: int,
        cost: float,
        ttl: float = 3600,  # 1 hour default
        **kwargs
    ) -> str:
        """Store response in cache"""
        
        key = self._generate_key(messages, **kwargs)
        
        # Extract strategy and provider from kwargs
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
        
        # Enforce max size
        if len(self.cache) > self.max_size:
            self._evict_oldest()
        
        return key
    
    def retrieve(self, messages: list[dict], **kwargs) -> Optional[CacheEntry]:
        """Retrieve cached response if available"""
        
        key = self._generate_key(messages, **kwargs)
        entry = self.cache.get(key)
        
        if entry and not entry.is_expired():
            self.hit_count += 1
            return entry
        
        self.miss_count += 1
        return None
    
    def _evict_oldest(self):
        """Remove oldest entry to make space"""
        if not self.cache:
            return
        
        # Find oldest entry
        oldest_key = min(self.cache.keys(), 
                        key=lambda k: self.cache[k].timestamp)
        del self.cache[oldest_key]
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        
        hit_rate = (self.hit_count / (self.hit_count + self.miss_count)) * 100 \
                   if (self.hit_count + self.miss_count) > 0 else 0
        
        return {
            'entries': len(self.cache),
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': round(hit_rate, 2),
            'size_bytes': sum(len(entry.response) for entry in self.cache.values())
        }
    
    def clear(self):
        """Clear all cache entries"""
        self.cache = {}
        self.hit_count = 0
        self.miss_count = 0
```

## Semantic Caching

### Advanced Cache with Semantic Matching
```python
# core/mascarade/cache/semantic_cache.py
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class SemanticCache(ResponseCache):
    """Cache with semantic similarity matching"""
    
    def __init__(self, similarity_threshold: float = 0.9):
        super().__init__()
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings: Dict[str, np.ndarray] = {}
        self.similarity_threshold = similarity_threshold
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        return self.model.encode(text, convert_to_numpy=True)
    
    def _get_semantic_key(self, messages: list[dict]) -> str:
        """Get semantic key from messages"""
        # Extract text content from messages
        text_content = " ".join(
            msg.get("content", "") 
            for msg in messages 
            if msg.get("role") == "user"
        )
        return text_content
    
    def store(self, messages: list[dict], response: str, **kwargs) -> str:
        """Store with semantic embedding"""
        
        key = super().store(messages, response, **kwargs)
        
        # Generate and store embedding
        semantic_text = self._get_semantic_key(messages)
        embedding = self._generate_embedding(semantic_text)
        self.embeddings[key] = embedding
        
        return key
    
    def retrieve_semantic(self, messages: list[dict], **kwargs) -> Optional[CacheEntry]:
        """Retrieve using semantic similarity"""
        
        # First try exact match
        exact_match = super().retrieve(messages, **kwargs)
        if exact_match:
            return exact_match
        
        # Try semantic match
        query_text = self._get_semantic_key(messages)
        query_embedding = self._generate_embedding(query_text)
        
        # Find most similar cached entry
        best_match = None
        best_similarity = 0
        
        for key, embedding in self.embeddings.items():
            similarity = cosine_similarity(
                [query_embedding],
                [embedding]
            )[0][0]
            
            if similarity > self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = key
        
        if best_match:
            entry = self.cache[best_match]
            if not entry.is_expired():
                self.hit_count += 1
                return entry
        
        self.miss_count += 1
        return None
```

## Cache Integration with Router

### Cached Router Implementation
```python
# core/mascarade/router/cached_router.py
from ..cache.cache import ResponseCache
from ..cache.semantic_cache import SemanticCache

class CachedRouter:
    """Router with caching capabilities"""
    
    def __init__(self, primary_router, use_semantic: bool = False):
        self.router = primary_router
        self.cache = SemanticCache() if use_semantic else ResponseCache()
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def send(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Send request with caching"""
        
        # Try cache first
        cached = self._try_cache(messages, **kwargs)
        if cached:
            self.cache_hits += 1
            
            # Return cached response in LLMResponse format
            return LLMResponse(
                content=cached.response,
                model=cached.provider,
                provider=cached.provider,
                usage={"total_tokens": cached.tokens}
            )
        
        self.cache_misses += 1
        
        # No cache hit - make actual request
        response = await self.router.send(messages, **kwargs)
        
        # Calculate cost for caching
        token_count = sum(response.usage.values())
        cost = self._calculate_cost(response.provider, token_count)
        
        # Store in cache
        self.cache.store(
            messages=messages,
            response=response.content,
            tokens=token_count,
            cost=cost,
            ttl=self._get_ttl(kwargs),
            **kwargs
        )
        
        return response
    
    def _try_cache(self, messages: list[dict], **kwargs) -> Optional[CacheEntry]:
        """Try to retrieve from cache"""
        
        # Don't cache if explicitly disabled
        if kwargs.get('cache', True) is False:
            return None
        
        # Use semantic cache if available
        if isinstance(self.cache, SemanticCache):
            return self.cache.retrieve_semantic(messages, **kwargs)
        
        return self.cache.retrieve(messages, **kwargs)
    
    def _calculate_cost(self, provider_name: str, tokens: int) -> float:
        """Calculate cost for caching"""
        
        # Get provider to access cost info
        provider = None
        for p in self.router._providers.values():
            if p.name == provider_name:
                provider = p
                break
        
        if not provider:
            return 0.0
        
        # Simplified cost calculation
        input_cost, output_cost = provider.cost_per_million
        return (tokens * (input_cost + output_cost)) / 2_000_000
    
    def _get_ttl(self, kwargs: dict) -> float:
        """Determine TTL based on request parameters"""
        
        # Custom TTL if specified
        if 'cache_ttl' in kwargs:
            return kwargs['cache_ttl']
        
        # Longer TTL for stable requests
        strategy = kwargs.get('strategy', 'best')
        if strategy == 'best':
            return 7200  # 2 hours
        
        return 3600  # 1 hour default
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        
        stats = self.cache.get_stats()
        stats.update({
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'savings': self._calculate_savings()
        })
        
        return stats
    
    def _calculate_savings(self) -> float:
        """Calculate estimated cost savings from caching"""
        
        # This would need actual cost tracking
        # For now, return a placeholder
        return 0.0
    
    def clear_cache(self):
        """Clear all cached entries"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
```

## Redis Cache Implementation

### Distributed Cache with Redis
```python
# core/mascarade/cache/redis_cache.py
import redis
import pickle
from typing import Optional

class RedisCache(ResponseCache):
    """Distributed cache using Redis"""
    
    def __init__(self, redis_url: str = 'redis://localhost:6379/0', 
                 max_size: int = 10000):
        super().__init__(max_size)
        self.redis = redis.Redis.from_url(redis_url)
        self.prefix = 'mascarade:cache:'
    
    def _get_redis_key(self, key: str) -> str:
        """Get full Redis key with prefix"""
        return f"{self.prefix}{key}"
    
    def store(self, messages: list[dict], response: str, **kwargs) -> str:
        """Store in Redis cache"""
        
        key = self._generate_key(messages, **kwargs)
        redis_key = self._get_redis_key(key)
        
        # Create cache entry
        entry = CacheEntry(
            response=response,
            tokens=kwargs.get('tokens', 0),
            cost=kwargs.get('cost', 0.0),
            timestamp=time.time(),
            ttl=kwargs.get('ttl', 3600),
            strategy=kwargs.get('strategy', 'best'),
            provider=kwargs.get('provider', 'unknown')
        )
        
        # Serialize and store
        serialized = pickle.dumps(entry)
        self.redis.setex(redis_key, int(entry.ttl), serialized)
        
        return key
    
    def retrieve(self, messages: list[dict], **kwargs) -> Optional[CacheEntry]:
        """Retrieve from Redis cache"""
        
        key = self._generate_key(messages, **kwargs)
        redis_key = self._get_redis_key(key)
        
        # Get from Redis
        serialized = self.redis.get(redis_key)
        
        if serialized:
            try:
                entry = pickle.loads(serialized)
                
                # Check expiration (Redis handles TTL, but double-check)
                if not entry.is_expired():
                    self.hit_count += 1
                    return entry
            except Exception:
                # Remove corrupted entry
                self.redis.delete(redis_key)
        
        self.miss_count += 1
        return None
    
    def clear(self):
        """Clear Redis cache"""
        
        # Find all keys with prefix
        keys = self.redis.keys(f"{self.prefix}*")
        
        # Delete all matching keys
        if keys:
            self.redis.delete(*keys)
        
        super().clear()
    
    def get_stats(self) -> dict:
        """Get Redis cache statistics"""
        
        stats = super().get_stats()
        stats.update({
            'redis_keys': self.redis.dbsize(),
            'redis_memory': self.redis.info('memory')
        })
        
        return stats
```

## Cache Invalidation Strategies

### Smart Cache Invalidation
```python
# core/mascarade/cache/invalidation.py
class CacheInvalidator:
    """Smart cache invalidation strategies"""
    
    def __init__(self, cache):
        self.cache = cache
    
    def invalidate_by_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        
        if isinstance(self.cache, RedisCache):
            # Redis implementation
            keys = self.cache.redis.keys(f"{self.cache.prefix}*{pattern}*")
            if keys:
                self.cache.redis.delete(*keys)
        else:
            # In-memory implementation
            to_delete = [
                key for key in self.cache.cache.keys() 
                if pattern in key
            ]
            for key in to_delete:
                del self.cache.cache[key]
    
    def invalidate_by_provider(self, provider_name: str):
        """Invalidate all entries from specific provider"""
        
        self.invalidate_by_pattern(f"provider:{provider_name}")
    
    def invalidate_by_strategy(self, strategy: str):
        """Invalidate all entries using specific strategy"""
        
        self.invalidate_by_pattern(f"strategy:{strategy}")
    
    def invalidate_old(self, max_age: float):
        """Invalidate entries older than max_age seconds"""
        
        cutoff = time.time() - max_age
        
        if isinstance(self.cache, RedisCache):
            # This would require scanning all keys
            # In production, better to use Redis TTL
            pass
        else:
            to_delete = [
                key for key, entry in self.cache.cache.items() 
                if entry.timestamp < cutoff
            ]
            for key in to_delete:
                del self.cache.cache[key]
    
    def invalidate_lru(self, count: int):
        """Invalidate least recently used entries"""
        
        if isinstance(self.cache, RedisCache):
            # Would need additional tracking
            pass
        else:
            # Sort by timestamp (oldest first)
            sorted_entries = sorted(
                self.cache.cache.items(),
                key=lambda x: x[1].timestamp
            )
            
            # Delete oldest 'count' entries
            for key, _ in sorted_entries[:count]:
                del self.cache.cache[key]
```

## API Endpoints for Cache Management

### Cache Management API
```typescript
// api/src/routes/cache.ts
import { Hono } from 'hono'
import { z } from 'zod'
import { zValidator } from '@hono/zod-validator'

const app = new Hono()

// Get cache statistics
app.get('/cache/stats', async (c) => {
  try {
    const stats = await coreClient.getCacheStats()
    return c.json(stats)
  } catch (error) {
    return c.json({ error: 'Failed to fetch cache stats' }, 500)
  }
})

// Clear cache
app.post('/cache/clear', async (c) => {
  try {
    await coreClient.clearCache()
    return c.json({ success: true, message: 'Cache cleared' })
  } catch (error) {
    return c.json({ error: 'Failed to clear cache' }, 500)
  }
})

// Invalidate by pattern
const invalidateSchema = z.object({
  pattern: z.string().min(1)
})

app.post('/cache/invalidate', zValidator('json', invalidateSchema), async (c) => {
  const { pattern } = c.req.valid('json')
  
  try {
    await coreClient.invalidateCache(pattern)
    return c.json({ success: true, pattern })
  } catch (error) {
    return c.json({ error: 'Failed to invalidate cache' }, 500)
  }
})

// Cache configuration
const configSchema = z.object({
  enabled: z.boolean().optional(),
  ttl: z.number().positive().optional(),
  max_size: z.number().positive().optional()
})

app.post('/cache/config', zValidator('json', configSchema), async (c) => {
  const config = c.req.valid('json')
  
  try {
    await coreClient.configureCache(config)
    return c.json({ success: true })
  } catch (error) {
    return c.json({ error: 'Failed to configure cache' }, 500)
  }
})

export default app
```

## Best Practices

1. **Cache Key Design**: Include all relevant parameters in cache keys
2. **TTL Management**: Set appropriate expiration times
3. **Size Limits**: Prevent unbounded cache growth
4. **Semantic Caching**: Use for similar but not identical requests
5. **Invalidation**: Implement smart invalidation strategies
6. **Monitoring**: Track cache hit/miss rates
7. **Cost Analysis**: Calculate actual cost savings
8. **Distributed Cache**: Use Redis for multi-instance deployments
9. **Cache Stampede**: Prevent thundering herd problems
10. **Security**: Validate all cached data before use