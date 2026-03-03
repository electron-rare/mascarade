# Router Strategies

## Overview
Mascarade's router implements multiple strategies for selecting LLM providers based on cost, speed, and quality requirements.

## Router Architecture

### File: `core/mascarade/router/__init__.py`
```python
from typing import Dict, Type
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.mistral import MistralProvider
from .providers.openai import OpenAIProvider

class LLMRouter:
    """Routes LLM requests based on strategy"""
    
    def __init__(self, strategy: str = "best"):
        self.strategy = strategy
        self.providers: Dict[str, LLMProvider] = {
            "claude": ClaudeProvider(),
            "mistral": MistralProvider(),
            "openai": OpenAIProvider()
        }
        
        # Strategy priorities
        self.strategy_map = {
            "best": ["claude", "openai", "mistral"],
            "cheapest": ["mistral", "openai", "claude"],
            "fastest": ["mistral", "claude", "openai"],
            "specific": []  # Will be set at runtime
        }
    
    def select_provider(self, strategy: str = None) -> LLMProvider:
        """Select provider based on strategy"""
        strategy = strategy or self.strategy
        
        if strategy == "specific":
            if not hasattr(self, 'specific_provider'):
                raise ValueError("Specific provider not set")
            return self.providers[self.specific_provider]
        
        for provider_id in self.strategy_map[strategy]:
            if self.providers[provider_id].is_available():
                return self.providers[provider_id]
        
        raise RuntimeError(f"No available provider for strategy: {strategy}")
    
    async def generate(
        self,
        prompt: str,
        strategy: str = None,
        **kwargs
    ) -> str:
        """Generate text using selected provider"""
        provider = self.select_provider(strategy)
        
        result = ""
        async for chunk in provider.generate(prompt, **kwargs):
            result += chunk
        
        return result
    
    async def chat(
        self,
        messages: list[dict],
        strategy: str = None,
        **kwargs
    ) -> dict:
        """Chat completion using selected provider"""
        provider = self.select_provider(strategy)
        return await provider.chat(messages, **kwargs)
```

## Provider Implementation

### Base Provider Interface
```python
# core/mascarade/router/providers/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMProvider(ABC):
    """Base class for all LLM providers"""
    
    def __init__(self):
        self.available = False
    
    def is_available(self) -> bool:
        """Check if provider is available"""
        return self.available
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Generate response stream"""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 1024
    ) -> dict:
        """Chat completion"""
        pass
```

## Strategy Details

### 1. Best Strategy
**Priority**: Claude → OpenAI → Mistral
**Use Case**: When quality is most important
**Implementation**:
```python
# Always tries Claude first, falls back to OpenAI, then Mistral
self.strategy_map["best"] = ["claude", "openai", "mistral"]
```

### 2. Cheapest Strategy
**Priority**: Mistral → OpenAI → Claude
**Use Case**: Cost-sensitive operations
**Implementation**:
```python
# Tries most affordable provider first
self.strategy_map["cheapest"] = ["mistral", "openai", "claude"]
```

### 3. Fastest Strategy
**Priority**: Mistral → Claude → OpenAI
**Use Case**: Real-time applications
**Implementation**:
```python
# Based on empirical response times
self.strategy_map["fastest"] = ["mistral", "claude", "openai"]
```

### 4. Specific Strategy
**Priority**: User-specified provider
**Use Case**: When specific provider is required
**Implementation**:
```python
# Set specific provider before use
router = LLMRouter(strategy="specific")
router.specific_provider = "claude"
```

## Provider Availability

### Health Check Pattern
```python
class ClaudeProvider(LLMProvider):
    def __init__(self):
        super().__init__()
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check API key and network connectivity"""
        try:
            # Check if API key is set
            if not os.getenv("CLAUDE_API_KEY"):
                return False
            
            # Optional: Ping API endpoint
            # This could be cached to avoid frequent checks
            return True
        except Exception:
            return False
```

## Advanced Routing

### Fallback with Retry
```python
async def generate_with_fallback(
    self,
    prompt: str,
    max_retries: int = 2
) -> str:
    """Generate with automatic fallback on failure"""
    
    strategies_to_try = [
        "best",
        "fastest", 
        "cheapest"
    ]
    
    last_error = None
    
    for strategy in strategies_to_try:
        for attempt in range(max_retries):
            try:
                return await self.generate(prompt, strategy=strategy)
            except Exception as e:
                last_error = e
                continue
    
    raise RuntimeError(f"All strategies failed: {str(last_error)}")
```

### Cost-Aware Routing
```python
class CostAwareRouter(LLMRouter):
    """Router that tracks token usage and costs"""
    
    def __init__(self):
        super().__init__()
        self.cost_tracking = {
            "claude": {"input": 0.01, "output": 0.03},  # per 1K tokens
            "openai": {"input": 0.005, "output": 0.015},
            "mistral": {"input": 0.002, "output": 0.006}
        }
        self.session_cost = 0
    
    async def generate(self, prompt: str, **kwargs) -> str:
        provider = self.select_provider()
        provider_id = self._get_provider_id(provider)
        
        # Estimate cost
        token_count = self._estimate_tokens(prompt)
        cost = (token_count * self.cost_tracking[provider_id]["input"])
        
        result = await super().generate(prompt, **kwargs)
        
        # Add output cost
        output_tokens = self._estimate_tokens(result)
        cost += (output_tokens * self.cost_tracking[provider_id]["output"])
        
        self.session_cost += cost
        
        return result
```

## Testing Strategies

### Unit Tests
```python
import pytest
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_router_strategies():
    router = LLMRouter()
    
    # Mock providers
    for provider in router.providers.values():
        provider.is_available = MagicMock(return_value=True)
        provider.generate = MagicMock(return_value=iter(["test response"]))
    
    # Test best strategy (should use Claude)
    with patch.object(router.providers["claude"], 'generate') as mock_claude:
        await router.generate("test", strategy="best")
        mock_claude.assert_called_once()
    
    # Test cheapest strategy (should use Mistral)
    with patch.object(router.providers["mistral"], 'generate') as mock_mistral:
        await router.generate("test", strategy="cheapest")
        mock_mistral.assert_called_once()
```

## Best Practices

1. **Fallback Strategy**: Always implement fallback logic
2. **Availability Checking**: Regular health checks for providers
3. **Cost Tracking**: Monitor token usage and costs
4. **Performance Monitoring**: Track response times by provider
5. **Configuration**: Make strategy priorities configurable
6. **Testing**: Test all strategies with mocked providers
7. **Documentation**: Clear docs on when to use each strategy