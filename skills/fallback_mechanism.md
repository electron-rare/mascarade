# Fallback Mechanism

## Overview
Robust fallback system for LLM providers to ensure high availability and reliability.

## Core Fallback System

### File: `core/mascarade/router/fallback.py`
```python
from typing import List, Optional, AsyncIterator
from dataclasses import dataclass
import time
import random

@dataclass
class FallbackConfig:
    """Configuration for fallback behavior"""
    max_retries: int = 3
    retry_delay: float = 0.5
    timeout: float = 30.0
    fallback_strategies: List[str] = None
    
    def __post_init__(self):
        if self.fallback_strategies is None:
            self.fallback_strategies = ['best', 'cheapest', 'fastest']

class FallbackRouter:
    """Router with automatic fallback capabilities"""
    
    def __init__(self, primary_router, config: FallbackConfig = None):
        self.router = primary_router
        self.config = config or FallbackConfig()
        self.failed_attempts = {}
    
    async def send_with_fallback(
        self,
        messages: list[dict],
        **kwargs
    ) -> Optional[LLMResponse]:
        """Send request with automatic fallback"""
        
        original_strategy = kwargs.get('strategy', 'best')
        original_provider = kwargs.get('provider')
        
        # Track retry attempts
        retry_count = 0
        last_error = None
        
        # Determine fallback sequence
        fallback_sequence = self._get_fallback_sequence(original_strategy, original_provider)
        
        for strategy, provider in fallback_sequence:
            retry_count += 1
            
            try:
                # Apply retry delay (with jitter)
                if retry_count > 1:
                    delay = self.config.retry_delay * (2 ** (retry_count - 1))
                    jitter = delay * 0.1 * random.random()
                    time.sleep(delay + jitter)
                
                # Update kwargs for this attempt
                attempt_kwargs = kwargs.copy()
                if strategy:
                    attempt_kwargs['strategy'] = strategy
                if provider:
                    attempt_kwargs['provider'] = provider
                
                return await self.router.send(messages, **attempt_kwargs)
                
            except Exception as e:
                last_error = e
                
                # Log failure
                provider_name = provider or strategy or 'unknown'
                if provider_name not in self.failed_attempts:
                    self.failed_attempts[provider_name] = 0
                self.failed_attempts[provider_name] += 1
                
                # Check if we should continue
                if retry_count >= self.config.max_retries:
                    break
                
                continue
        
        # All attempts failed
        raise RuntimeError(
            f"All fallback attempts failed after {retry_count} tries. "
            f"Last error: {str(last_error)}"
        )
    
    async def stream_with_fallback(
        self,
        messages: list[dict],
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream with automatic fallback"""
        
        original_strategy = kwargs.get('strategy', 'best')
        original_provider = kwargs.get('provider')
        
        fallback_sequence = self._get_fallback_sequence(original_strategy, original_provider)
        
        for strategy, provider in fallback_sequence:
            try:
                attempt_kwargs = kwargs.copy()
                if strategy:
                    attempt_kwargs['strategy'] = strategy
                if provider:
                    attempt_kwargs['provider'] = provider
                
                async for chunk in self.router.stream(messages, **attempt_kwargs):
                    yield chunk
                return  # Success - exit after first working provider
                
            except Exception as e:
                # Log failure and continue to next fallback
                provider_name = provider or strategy or 'unknown'
                if provider_name not in self.failed_attempts:
                    self.failed_attempts[provider_name] = 0
                self.failed_attempts[provider_name] += 1
                
                # Small delay before next attempt
                time.sleep(self.config.retry_delay)
                continue
        
        # If we get here, all attempts failed
        raise RuntimeError("All fallback attempts failed for streaming request")
    
    def _get_fallback_sequence(
        self,
        original_strategy: str,
        original_provider: Optional[str]
    ) -> List[tuple]:
        """Generate fallback sequence based on original request"""
        
        sequence = []
        
        # First try: original request
        if original_provider:
            sequence.append((None, original_provider))
        else:
            sequence.append((original_strategy, None))
        
        # Additional attempts: try other strategies
        for strategy in self.config.fallback_strategies:
            if strategy != original_strategy:
                sequence.append((strategy, None))
        
        # Final attempt: try specific providers if available
        available_providers = self.router.available_providers
        for provider in available_providers:
            if not original_provider or provider != original_provider:
                sequence.append((None, provider))
        
        return sequence
    
    def get_failure_stats(self) -> dict:
        """Get statistics on failed attempts"""
        return {
            'failed_attempts': dict(self.failed_attempts),
            'total_failures': sum(self.failed_attempts.values())
        }
    
    def reset_failure_stats(self):
        """Reset failure tracking"""
        self.failed_attempts = {}
```

## Provider Health Monitoring

### Health Check System
```python
# core/mascarade/router/health.py
import time
from typing import Dict

class ProviderHealthMonitor:
    """Monitor provider health and availability"""
    
    def __init__(self, router):
        self.router = router
        self.health_status: Dict[str, dict] = {}
        self.check_interval = 60  # seconds
        self.last_check = 0
    
    def check_provider_health(self, provider_name: str) -> dict:
        """Check health of a specific provider"""
        
        if time.time() - self.last_check < self.check_interval:
            return self.health_status.get(provider_name, {'status': 'unknown'})
        
        try:
            # Simple health check - could be enhanced
            provider = self.router._providers.get(provider_name)
            if not provider:
                return {'status': 'unavailable', 'error': 'Provider not configured'}
            
            # Test basic connectivity
            start_time = time.time()
            test_prompt = "Health check: ${time.time()}"
            
            # Use a very short timeout
            response = await provider.send(
                [{"role": "user", "content": test_prompt}],
                max_tokens=5,
                timeout=5.0
            )
            
            response_time = time.time() - start_time
            
            self.health_status[provider_name] = {
                'status': 'healthy',
                'response_time': response_time,
                'last_check': time.time(),
                'error_rate': 0.0
            }
            
            return self.health_status[provider_name]
            
        except Exception as e:
            self.health_status[provider_name] = {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': time.time()
            }
            return self.health_status[provider_name]
    
    def get_health_summary(self) -> dict:
        """Get health summary for all providers"""
        
        summary = {}
        for provider_name in self.router.available_providers:
            summary[provider_name] = self.check_provider_health(provider_name)
        
        return summary
    
    def should_use_provider(self, provider_name: str) -> bool:
        """Determine if provider should be used based on health"""
        
        health = self.health_status.get(provider_name, {}).get('status')
        
        # Only use healthy providers
        return health == 'healthy'
```

## Circuit Breaker Pattern

### Circuit Breaker Implementation
```python
# core/mascarade/router/circuit_breaker.py
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker for provider failures"""
    
    def __init__(
        self,
        max_failures: int = 5,
        reset_timeout: int = 60,
        half_open_after: int = 30
    ):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.half_open_after = half_open_after
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.last_success_time = 0
    
    def record_success(self):
        """Record a successful request"""
        self.failure_count = 0
        self.last_success_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """Record a failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.max_failures:
            self.state = CircuitState.OPEN
    
    def can_attempt(self) -> bool:
        """Check if request should be attempted"""
        
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if enough time has passed to try half-open
            if time.time() - self.last_failure_time > self.half_open_after:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'last_failure': self.last_failure_time,
            'last_success': self.last_success_time,
            'reset_in': max(0, (self.last_failure_time + self.reset_timeout) - time.time()) 
                        if self.state == CircuitState.OPEN else 0
        }
```

## Integration with Router

### Enhanced Router with Fallback
```python
# core/mascarade/router/router.py
from .fallback import FallbackRouter, FallbackConfig
from .health import ProviderHealthMonitor

class EnhancedRouter:
    """Router with fallback and health monitoring"""
    
    def __init__(self):
        self.primary_router = Router()
        self.fallback_router = FallbackRouter(self.primary_router)
        self.health_monitor = ProviderHealthMonitor(self.primary_router)
        
        # Circuit breakers for each provider
        self.circuit_breakers = {
            provider: CircuitBreaker()
            for provider in self.primary_router.available_providers
        }
    
    async def send(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Send with fallback and circuit breaker"""
        
        # Check circuit breakers
        available_providers = self._get_available_providers()
        
        if not available_providers:
            raise RuntimeError("All providers are currently unavailable")
        
        # Use fallback router
        return await self.fallback_router.send_with_fallback(messages, **kwargs)
    
    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Stream with fallback"""
        
        available_providers = self._get_available_providers()
        
        if not available_providers:
            raise RuntimeError("All providers are currently unavailable")
        
        async for chunk in self.fallback_router.stream_with_fallback(messages, **kwargs):
            yield chunk
    
    def _get_available_providers(self) -> list:
        """Get list of providers that can be used"""
        
        available = []
        for provider in self.primary_router.available_providers:
            breaker = self.circuit_breakers.get(provider)
            if breaker and breaker.can_attempt():
                available.append(provider)
        
        return available
    
    def get_health_status(self) -> dict:
        """Get comprehensive health status"""
        
        return {
            'providers': self.health_monitor.get_health_summary(),
            'circuit_breakers': {
                name: cb.get_status()
                for name, cb in self.circuit_breakers.items()
            },
            'fallback_stats': self.fallback_router.get_failure_stats()
        }
```

## API Endpoints

### Health and Fallback API
```typescript
// api/src/routes/health.ts
import { Hono } from 'hono'

const app = new Hono()

// System health check
app.get('/health', async (c) => {
  try {
    const health = await coreClient.getHealthStatus()
    
    // Overall system status
    const all_healthy = Object.values(health.providers).every(
      p => p.status === 'healthy'
    )
    
    return c.json({
      status: all_healthy ? 'healthy' : 'degraded',
      providers: health.providers,
      circuit_breakers: health.circuit_breakers,
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    return c.json({
      status: 'unhealthy',
      error: error.message,
      timestamp: new Date().toISOString()
    }, 500)
  }
})

// Provider-specific health
app.get('/health/:provider', async (c) => {
  const provider = c.req.param('provider')
  
  try {
    const health = await coreClient.getProviderHealth(provider)
    return c.json(health)
  } catch (error) {
    return c.json({
      status: 'error',
      provider,
      error: error.message
    }, 404)
  }
})

// Reset circuit breakers (admin)
app.post('/health/reset', async (c) => {
  try {
    await coreClient.resetCircuitBreakers()
    return c.json({ success: true })
  } catch (error) {
    return c.json({ error: 'Failed to reset circuit breakers' }, 500)
  }
})

export default app
```

## Best Practices

1. **Exponential Backoff**: Implement delays between retries
2. **Circuit Breakers**: Prevent cascading failures
3. **Health Monitoring**: Regular provider health checks
4. **Failure Tracking**: Monitor and log fallback attempts
5. **Strategy Diversity**: Try different strategies on failure
6. **Timeout Management**: Respect timeouts during fallback
7. **Resource Limits**: Prevent infinite retry loops
8. **Alerting**: Notify on repeated failures
9. **Metrics Integration**: Track fallback usage in metrics
10. **Configuration**: Make fallback parameters configurable