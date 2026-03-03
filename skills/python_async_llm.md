# Python Async LLM Provider

## Overview
Mascarade uses async Python for LLM provider implementations to handle concurrent requests efficiently.

## Key Components

### Base Provider (`core/mascarade/router/providers/base.py`)
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
import httpx

class LLMProvider(ABC):
    """Base class for all LLM providers"""
    
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

## Implementation Pattern

### Async HTTP Client
```python
# Use httpx.AsyncClient for all external API calls
client = httpx.AsyncClient(
    timeout=30.0,
    headers={"Authorization": f"Bearer {self.api_key}"}
)
```

### Streaming Response
```python
async def generate(self, prompt: str) -> AsyncIterator[str]:
    async with client.stream("POST", self.api_url, json={"prompt": prompt}) as response:
        async for chunk in response.aiter_text():
            yield chunk
```

### Error Handling
```python
try:
    response = await client.post(url, json=payload)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    raise LLMProviderError(f"API error: {e.response.text}")
except httpx.RequestError as e:
    raise LLMProviderError(f"Request failed: {str(e)}")
```

## Testing Async Code

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_provider_generate():
    provider = ClaudeProvider(api_key="test")
    provider.client.post = AsyncMock(return_value=MockResponse())
    
    result = []
    async for chunk in provider.generate("test prompt"):
        result.append(chunk)
    
    assert len(result) > 0
```

## Best Practices

1. Always use `async with` for resource management
2. Implement proper timeout handling (30s default)
3. Stream responses for better UX
4. Handle API rate limits gracefully
5. Use Pydantic models for request/response validation