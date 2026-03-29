---
applyTo: core/**/*.py
description: "Use when modifying Python code in core. Enforces async-first patterns and targeted validation."
---

# Core Python Instructions

## Core Principles

- **Async-first I/O**: All network/disk operations must be `async def` with `await`.
- **Provider abstraction**: Create new providers by subclassing `LLMProvider` (see `core/mascarade/router/providers/base.py`).
- **Registry pattern**: Register agents via `AgentRegistry` — no inheritance for agent definitions.
- **Pydantic v2**: All data models use `BaseModel` with field validation; no dataclasses for API schemas.
- **Explicit typing**: Avoid `Any` or implicit `Unknown`; use type hints on all function signatures.
- **Validation at boundaries**: Only validate user input (auth), external API responses, and config; trust internal types.

## Async Patterns (Critical)

### pytest WITHOUT @pytest.mark.asyncio
```python
# pyproject.toml sets asyncio_mode = "auto" — tests run async automatically
# ✅ CORRECT:
async def test_agent_coordination():
    result = await engine.coordinate(request, context)
    assert result.status == "success"

# ❌ DON'T DO THIS (breaks collection):
@pytest.mark.asyncio
async def test_agent_coordination(): ...
```

### conftest.py node_engine Test Skipping
```bash
# core/conftest.py ignores tests/test_node_engine/* by default
# To run node_engine tests:
cd core && python -m pytest tests/test_node_engine.py -v
```

## Pattern Examples

### Provider Implementation
```python
from mascarade.router.providers.base import LLMProvider

class MyProvider(LLMProvider):
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        return await self._call_api(prompt)
```

### Agent Registry Lookup
```python
from mascarade.agents import AgentRegistry

registry = AgentRegistry()
agents = registry.filter_by_cluster("electronics")
best_agent = registry.get_best_for_task("kicad-design", domain="electronics")
```

### Configuration Cascade  
```python
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    ollama_host: str = "http://localhost:11434"
    # Overrides via env: OLLAMA_HOST=http://tower.local:11434
```

## Critical Gotchas

### 1. Ollama MetalGPUError (Not Blocking)
- File: `core/mascarade/router/providers/ollama.py`
- Behavior: Falls back to P2P mesh; not a critical error.

### 2. VRAM Routing & Model Sizes
- File: `core/mascarade/router/model_sizes.py`
- `qwen3:4b` → 4GB (Tower CPU); `qwen3:8b` → 12GB (KXKM-AI GPU)

### 3. Redis/Qdrant Cache Failures
- RAG pipeline auto-fallback: Redis down → Qdrant; both down → web search.

### 4. SSH Tunnels for KXKM-AI GPU
- GPU inference requires `clems@192.168.0.120:22` tunnel.

### 5. P2P Mesh Routing
- File: `core/mascarade/p2p/cluster.py`
- Routes by VRAM + latency; don't hardcode machine targets.

## Validation Commands

```bash
cd core
python -m pytest                        # All tests
python -m pytest tests/test_router.py   # Validate providers
ruff check mascarade/ tests/            # Linting
black mascarade/ tests/                 # Formatting
mypy mascarade/                         # Type checking
```