# Apple Intelligence Integration — Technical Specification

> Last updated: 2026-03-21

## Overview

This specification defines how Mascarade integrates Apple Silicon-native inference runtimes and Apple Intelligence APIs as first-class LLM providers. The goal is to leverage local Mac hardware for fast, private, zero-cost inference while maintaining the unified router interface.

---

## 1. MLX-LM Provider

### Purpose

MLX-LM is Apple's native ML framework optimized for Apple Silicon (M1-M5). It provides an OpenAI-compatible HTTP server, making it a drop-in provider for Mascarade's router.

### Architecture

```
mascarade-core (FastAPI)
  └── router/providers/mlx_lm.py
        └── httpx.AsyncClient
              └── MLX-LM Server (:8080)
                    └── MLX Framework
                          └── Apple Silicon (Metal GPU)
```

### Provider Implementation: `mlx_lm.py`

```python
# core/mascarade/router/providers/mlx_lm.py

from mascarade.router.providers.base import LLMProvider, LLMResponse

class MLXLMProvider(LLMProvider):
    """MLX-LM provider for Apple Silicon native inference."""

    name = "mlx-lm"
    supports_streaming = True

    def __init__(self, config: dict):
        self.base_url = config.get("MLX_LM_BASE_URL", "http://localhost:8080")
        self.default_model = config.get("MLX_LM_MODEL", "mlx-community/Qwen2.5-Coder-1.5B-4bit")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    async def send(self, messages: list, model: str | None = None, **kwargs) -> LLMResponse:
        """Send chat completion request to MLX-LM server."""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "stream": False,
        }
        response = await self.client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return self._parse_openai_response(data)

    async def send_streaming(self, messages: list, model: str | None = None, **kwargs):
        """Stream chat completion from MLX-LM server (SSE)."""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "stream": True,
        }
        async with self.client.stream("POST", "/v1/chat/completions", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    yield self._parse_streaming_chunk(line[6:])

    async def list_models(self) -> list[str]:
        """List available models on the MLX-LM server."""
        response = await self.client.get("/v1/models")
        data = response.json()
        return [m["id"] for m in data.get("data", [])]

    async def health_check(self) -> bool:
        try:
            resp = await self.client.get("/v1/models")
            return resp.status_code == 200
        except Exception:
            return False
```

### Configuration

```env
# .env
MLX_LM_ENABLED=true
MLX_LM_BASE_URL=http://localhost:8080
MLX_LM_MODEL=mlx-community/Qwen2.5-Coder-1.5B-4bit
MLX_LM_MAX_TOKENS=4096
```

### Server Setup

```bash
# Install MLX-LM
pip install mlx-lm

# Start OpenAI-compatible server
mlx_lm.server \
  --model mlx-community/Qwen2.5-Coder-1.5B-4bit \
  --host 0.0.0.0 \
  --port 8080

# Verify
curl http://localhost:8080/v1/models
```

### Supported Models (MLX Format)

| Model | Size | Quantization | RAM Required | Tokens/sec (M3 Max) |
|-------|------|-------------|-------------|---------------------|
| Qwen2.5-Coder-1.5B | 941MB | 4-bit | 2GB | ~80 |
| Qwen2.5-7B | 4.1GB | 4-bit | 6GB | ~40 |
| Llama-3.1-8B | 4.5GB | 4-bit | 6GB | ~35 |
| Mistral-7B-v0.3 | 4.1GB | 4-bit | 6GB | ~38 |
| Codestral-22B | 12GB | 4-bit | 16GB | ~15 |

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Time-to-first-token (TTFT) | < 200ms | 1.5B model, 4-bit |
| Throughput | > 60 tok/s | M3 Max, 1.5B model |
| Memory overhead | < 500MB | Beyond model weight |
| Cold start | < 3s | Model already loaded |
| Warm request | < 50ms TTFT | Subsequent requests |

---

## 2. Exo Distributed Inference

### Purpose

Exo enables splitting a single large model across multiple Apple Silicon devices on the same network, enabling inference of models too large for any single machine.

### Architecture

```
mascarade-core (FastAPI)
  └── router/providers/exo.py
        └── httpx.AsyncClient
              └── Exo Coordinator (:52415)
                    ├── Mac 1 (shard 0-3)  ─── Metal GPU
                    ├── Mac 2 (shard 4-7)  ─── Metal GPU
                    └── Mac 3 (shard 8-11) ─── Metal GPU
```

### Provider Implementation: `exo.py`

```python
# core/mascarade/router/providers/exo.py

from mascarade.router.providers.base import LLMProvider, LLMResponse

class ExoProvider(LLMProvider):
    """Exo distributed inference provider for Mac clusters."""

    name = "exo"
    supports_streaming = True

    def __init__(self, config: dict):
        self.base_url = config.get("EXO_BASE_URL", "http://localhost:52415")
        self.default_model = config.get("EXO_MODEL", "llama-3.1-70b")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def send(self, messages: list, model: str | None = None, **kwargs) -> LLMResponse:
        """Send to Exo cluster (OpenAI-compatible)."""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }
        response = await self.client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        return self._parse_openai_response(response.json())

    async def cluster_status(self) -> dict:
        """Get Exo cluster topology and shard assignments."""
        response = await self.client.get("/cluster/status")
        return response.json()

    async def health_check(self) -> bool:
        try:
            status = await self.cluster_status()
            return status.get("ready", False)
        except Exception:
            return False
```

### Configuration

```env
# .env
EXO_ENABLED=true
EXO_BASE_URL=http://localhost:52415
EXO_MODEL=llama-3.1-70b
EXO_DISCOVERY=bonjour
EXO_TIMEOUT=300
```

### Cluster Setup

```bash
# Install Exo on each Mac
pip install exo

# Node 1 (coordinator) — starts discovery
exo run llama-3.1-70b --discovery bonjour

# Nodes 2-N automatically join via Bonjour/mDNS
# Exo handles shard assignment based on available RAM
```

### Model Sharding Strategy

| Model | Total Size | Min Nodes (M3 Max 96GB) | Min Nodes (M2 24GB) |
|-------|-----------|------------------------|---------------------|
| Llama-3.1-8B | 16GB FP16 | 1 | 1 |
| Llama-3.1-70B | 140GB FP16 | 2 | 6 |
| Qwen2.5-72B | 144GB FP16 | 2 | 6 |
| Llama-3.1-405B | 810GB FP16 | 9 | 34 |

### Integration with P2P Mesh

Exo discovery can be bridged with Mascarade's existing P2P mesh:

```python
# In P2P capabilities advertisement
capabilities = {
    "gpu": "apple-metal",
    "ram_gb": 96,
    "exo_available": True,
    "exo_shard_capacity": 48,  # GB available for shards
}
```

The router strategy engine gains an `exo_distributed` option:
- Query P2P mesh for nodes with `exo_available=True`
- Calculate total available shard capacity
- Route large models to Exo when enough cluster RAM is available
- Fallback to cloud provider if cluster is insufficient

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| TTFT (70B, 2 nodes) | < 2s | Cross-device tensor transfer |
| Throughput (70B, 2 nodes) | > 15 tok/s | M3 Max cluster |
| Shard sync overhead | < 500ms | Per-layer communication |
| Discovery time | < 5s | Bonjour mDNS |

---

## 3. Apple Foundation Models — Swift Bridge

### Purpose

Apple Foundation Models (AFM) provide a 3B parameter on-device model integrated into macOS 26+. Access requires Swift and the Foundation framework. This spec defines the Python-Swift bridge.

### Architecture

```
mascarade-core (FastAPI)
  └── router/providers/apple_fm.py
        └── Unix Domain Socket / HTTP
              └── afm-bridge (Swift executable)
                    └── FoundationModels.framework
                          └── Apple Neural Engine (ANE)
```

### Swift Bridge: `afm-bridge`

```swift
// tools/afm-bridge/Sources/main.swift

import Foundation
import FoundationModels

@main
struct AFMBridge {
    static func main() async throws {
        let server = AFMServer(port: 8090)
        try await server.run()
    }
}

struct AFMServer {
    let port: Int
    let session: LanguageModelSession

    init(port: Int) {
        self.port = port
        self.session = LanguageModelSession()
    }

    func handleChatCompletion(messages: [[String: String]]) async throws -> String {
        let prompt = messages.map { $0["content"] ?? "" }.joined(separator: "\n")
        let response = try await session.respond(to: prompt)
        return response.content
    }
}
```

### Python Provider: `apple_fm.py`

```python
# core/mascarade/router/providers/apple_fm.py

from mascarade.router.providers.base import LLMProvider, LLMResponse

class AppleFoundationModelsProvider(LLMProvider):
    """Apple Foundation Models (on-device 3B) via Swift bridge."""

    name = "apple-fm"
    supports_streaming = True

    def __init__(self, config: dict):
        self.base_url = config.get("AFM_BRIDGE_URL", "http://localhost:8090")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def send(self, messages: list, model: str | None = None, **kwargs) -> LLMResponse:
        payload = {
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        response = await self.client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        return self._parse_openai_response(response.json())

    async def health_check(self) -> bool:
        try:
            resp = await self.client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def is_available() -> bool:
        """Check if running on macOS 26+ with AFM support."""
        import platform
        if platform.system() != "Darwin":
            return False
        major = int(platform.mac_ver()[0].split(".")[0])
        return major >= 26
```

### Configuration

```env
# .env
AFM_ENABLED=true
AFM_BRIDGE_URL=http://localhost:8090
AFM_BRIDGE_PATH=/usr/local/bin/afm-bridge
AFM_MAX_TOKENS=4096
```

### Capabilities and Limitations

| Capability | Value |
|-----------|-------|
| Model size | ~3B parameters |
| Context window | 4096 tokens (estimated) |
| Runtime | Apple Neural Engine (ANE) |
| OS requirement | macOS 26+ |
| Languages | English primary, multilingual |
| Modalities | Text generation, summarization, code |
| Privacy | Fully on-device, no network |
| Cost | $0 per token |

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| TTFT | < 100ms | ANE optimized |
| Throughput | > 100 tok/s | ANE, 3B model |
| Memory | < 4GB | Compressed model |
| Cold start | < 1s | System-level caching |

---

## 4. App Intents — Siri Integration

### Purpose

App Intents allow Mascarade to register actions with Siri, enabling voice-driven LLM orchestration.

### Architecture

```
User (voice)
  └── Siri
        └── App Intents Framework
              └── MascaradeIntents (Swift App)
                    └── HTTP Client
                          └── mascarade-api (:3000)
                                └── mascarade-core (:8100)
```

### Intent Definitions

```swift
// tools/mascarade-intents/Sources/Intents/AskMascaradeIntent.swift

import AppIntents

struct AskMascaradeIntent: AppIntent {
    static var title: LocalizedStringResource = "Ask Mascarade"
    static var description: IntentDescription = "Send a prompt to Mascarade LLM orchestrator"

    @Parameter(title: "Prompt")
    var prompt: String

    @Parameter(title: "Strategy", default: "best")
    var strategy: String

    func perform() async throws -> some IntentResult & ReturnsValue<String> {
        let client = MascaradeClient(
            baseURL: "http://localhost:3000",
            apiKey: ProcessInfo.processInfo.environment["MASCARADE_API_KEY"] ?? ""
        )
        let response = try await client.chatCompletion(
            messages: [["role": "user", "content": prompt]],
            strategy: strategy
        )
        return .result(value: response)
    }
}

struct RunAgentIntent: AppIntent {
    static var title: LocalizedStringResource = "Run Mascarade Agent"
    static var description: IntentDescription = "Execute a specialized agent"

    @Parameter(title: "Agent Name")
    var agentName: String

    @Parameter(title: "Task Description")
    var task: String

    func perform() async throws -> some IntentResult & ReturnsValue<String> {
        let client = MascaradeClient(baseURL: "http://localhost:3000")
        let response = try await client.agentSend(agent: agentName, message: task)
        return .result(value: response)
    }
}
```

### Supported Siri Commands

| Command | Intent | Route |
|---------|--------|-------|
| "Hey Siri, ask Mascarade..." | AskMascaradeIntent | POST /v1/chat/completions |
| "Hey Siri, run the KiCad agent..." | RunAgentIntent | POST /v1/agents/send |
| "Hey Siri, check Mascarade status" | StatusIntent | GET /v1/version |
| "Hey Siri, list Mascarade models" | ListModelsIntent | GET /v1/models |

---

## 5. Migration Path: CoreML to Core AI

### Current State

The existing `apple_coreml.py` provider uses CoreML for on-device inference with manually converted `.mlpackage` models.

### Migration Phases

```
Phase 0 (Current)     Phase 1 (Q2 2026)     Phase 2 (Q3 2026)     Phase 3 (Q4 2026)
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ apple_coreml.py  │  │ + mlx_lm.py      │  │ + apple_fm.py    │  │ + core_ai.py     │
│ CoreML manual    │  │ MLX-LM server    │  │ AFM 3B bridge    │  │ Core AI unified  │
│ .mlpackage       │  │ OpenAI-compat    │  │ Swift IPC        │  │ All Apple APIs   │
│                  │  │ + exo.py         │  │                  │  │                  │
│                  │  │ Distributed      │  │                  │  │ Deprecate:       │
│                  │  │                  │  │                  │  │  - apple_coreml   │
│                  │  │                  │  │                  │  │  - apple_fm       │
└──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

| Phase | Timeline | Action | Risk |
|-------|----------|--------|------|
| 0 | Now | CoreML provider operational | Low — stable |
| 1 | Q2 2026 | Add MLX-LM + Exo providers | Low — OpenAI-compatible, no breaking changes |
| 2 | Q3 2026 (post-WWDC) | Add Apple FM Swift bridge | Medium — new Swift dependency |
| 3 | Q4 2026 | Unified Core AI provider, deprecate CoreML | Medium — depends on Core AI SDK scope |

### Deprecation Policy

- `apple_coreml.py` will emit deprecation warnings starting Phase 2
- Full removal in Phase 3 + 6 months (per API stability contract)
- Router auto-migrates `provider=apple-coreml` to `provider=core-ai` with warning header

---

## 6. Router Strategy Updates

### New Strategy: `local-first`

```python
class LocalFirstStrategy:
    """Prefer local Apple Silicon inference, fallback to cloud."""

    priority_order = [
        "mlx-lm",       # Fastest local, quantized models
        "apple-fm",     # On-device 3B, zero cost
        "exo",          # Distributed local cluster
        "ollama",       # Ollama local
        "llama-cpp",    # llama.cpp local
        "apple-coreml", # Legacy CoreML
        # Cloud fallbacks
        "claude",
        "openai",
        "mistral",
    ]
```

### Device Detection

```python
async def detect_apple_capabilities() -> dict:
    """Detect available Apple Silicon capabilities."""
    import platform
    import subprocess

    caps = {
        "is_apple_silicon": False,
        "chip": None,
        "ram_gb": 0,
        "gpu_cores": 0,
        "ane_available": False,
        "mlx_available": False,
        "exo_available": False,
        "afm_available": False,
    }

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return caps

    caps["is_apple_silicon"] = True

    # Detect chip
    result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                          capture_output=True, text=True)
    caps["chip"] = result.stdout.strip()

    # RAM
    result = subprocess.run(["sysctl", "-n", "hw.memsize"],
                          capture_output=True, text=True)
    caps["ram_gb"] = int(result.stdout.strip()) // (1024**3)

    # Check framework availability
    caps["mlx_available"] = _check_import("mlx")
    caps["exo_available"] = _check_import("exo")
    caps["ane_available"] = True  # All Apple Silicon has ANE
    caps["afm_available"] = int(platform.mac_ver()[0].split(".")[0]) >= 26

    return caps
```

### Auto-Registration

On startup, Mascarade core will:

1. Run `detect_apple_capabilities()`
2. If MLX is available and `MLX_LM_ENABLED=true`, register `mlx-lm` provider
3. If Exo is available and `EXO_ENABLED=true`, register `exo` provider
4. If AFM is available and `AFM_ENABLED=true`, launch `afm-bridge` and register `apple-fm` provider
5. Advertise capabilities to P2P mesh

---

## 7. API Contract

All Apple Intelligence providers implement the standard Mascarade provider interface and expose the frozen `/v1/chat/completions` contract.

### Endpoints

| Endpoint | Method | Provider | Notes |
|----------|--------|----------|-------|
| `/v1/chat/completions` | POST | All | OpenAI-compatible, strategy=local-first |
| `/v1/models` | GET | All | Lists local + cloud models |
| `/v1/providers/apple/status` | GET | — | Apple capabilities summary |
| `/v1/providers/exo/cluster` | GET | Exo | Cluster topology |

### Request Format (unchanged)

```json
{
  "model": "mlx-community/Qwen2.5-Coder-1.5B-4bit",
  "messages": [
    {"role": "user", "content": "Write a Python function..."}
  ],
  "temperature": 0.7,
  "max_tokens": 2048,
  "stream": false
}
```

### Response Metadata (extended)

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "choices": [...],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 128,
    "total_tokens": 170
  },
  "mascarade": {
    "provider": "mlx-lm",
    "model": "mlx-community/Qwen2.5-Coder-1.5B-4bit",
    "strategy": "local-first",
    "runtime": "apple-silicon",
    "device": "M3 Max",
    "latency_ms": 340,
    "cost_usd": 0.0,
    "cache_hit": false
  }
}
```

---

## 8. Testing Plan

| Test | Type | Provider | Notes |
|------|------|----------|-------|
| MLX-LM provider unit tests | Unit | mlx-lm | Mock HTTP |
| MLX-LM integration (live server) | Integration | mlx-lm | Requires Apple Silicon |
| Exo provider unit tests | Unit | exo | Mock HTTP |
| Exo cluster integration | Integration | exo | Requires 2+ Macs |
| AFM bridge unit tests | Unit | apple-fm | Mock Swift bridge |
| AFM integration | Integration | apple-fm | Requires macOS 26+ |
| Router local-first strategy | Unit | — | Strategy selection |
| Device detection | Unit | — | Platform mocking |
| Auto-registration | Integration | — | Full startup flow |
| Fallback cloud on missing local | Integration | — | Graceful degradation |

### Test Commands

```bash
# Unit tests (all platforms)
cd core && python -m pytest tests/test_mlx_lm_provider.py -v
cd core && python -m pytest tests/test_exo_provider.py -v
cd core && python -m pytest tests/test_apple_fm_provider.py -v

# Integration tests (Apple Silicon only)
cd core && python -m pytest tests/test_apple_integration.py -v --apple-silicon

# Strategy tests
cd core && python -m pytest tests/test_local_first_strategy.py -v
```
