"""Local lightweight server — Fake Ollama + Mistral HTTP API + P2P routing.

Only loads the minimal set of dependencies needed for:
- Fake Ollama API (ollama_compat)
- Mistral via HTTP (no SDK, just httpx)
- P2P forwarding to peers

Start with:
    PYTHONPATH=. .venv/bin/uvicorn mascarade.local_server:app --host 0.0.0.0 --port 11434
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mascarade.local")

# ── Config ──────────────────────────────────────────────────────────

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = os.getenv("MISTRAL_API_BASE", "https://api.mistral.ai/v1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# P2P peers to forward to when model is unavailable locally
P2P_PEERS = [
    p.strip()
    for p in os.getenv("P2P_PEERS", "").split(",")
    if p.strip()
]

# ── Provider registry ────────────────────────────────────────────────

PROVIDERS: dict[str, dict] = {}

if MISTRAL_API_KEY:
    PROVIDERS["mistral"] = {
        "base_url": MISTRAL_BASE_URL,
        "api_key": MISTRAL_API_KEY,
        "models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest",
                    "mistral-medium-latest", "devstral-latest", "magistral-medium-latest"],
    }
if ANTHROPIC_API_KEY:
    PROVIDERS["claude"] = {
        "base_url": "https://api.anthropic.com",
        "api_key": ANTHROPIC_API_KEY,
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514",
                    "claude-3-5-sonnet-20241022"],
    }
if OPENAI_API_KEY:
    PROVIDERS["openai"] = {
        "base_url": "https://api.openai.com/v1",
        "api_key": OPENAI_API_KEY,
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
    }

logger.info("Providers: %s", list(PROVIDERS.keys()))


# ── Mistral HTTP client (no SDK) ────────────────────────────────────

async def mistral_chat(
    messages: list[dict],
    model: str = "mistral-large-latest",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    stream: bool = False,
) -> dict | AsyncIterator[str]:
    """Call Mistral API via plain HTTP."""
    if not MISTRAL_API_KEY:
        raise HTTPException(503, "MISTRAL_API_KEY not configured")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    client = httpx.AsyncClient(timeout=180.0)

    if not stream:
        resp = await client.post(
            f"{MISTRAL_BASE_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
        )
        resp.raise_for_status()
        data = resp.json()
        await client.aclose()
        return data
    else:
        # Streaming
        async def _stream():
            async with client.stream(
                "POST",
                f"{MISTRAL_BASE_URL}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        yield chunk
            await client.aclose()

        return _stream()


# ── P2P forwarding ──────────────────────────────────────────────────

async def try_p2p_forward(
    messages: list[dict],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> dict | None:
    """Try to forward to a P2P peer's fake Ollama endpoint."""
    for peer in P2P_PEERS:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{peer}/ollama/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature, "num_predict": max_tokens},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    data["_routed_via"] = peer
                    return data
        except Exception as exc:
            logger.warning("P2P peer %s unreachable: %s", peer, exc)
    return None


# ── Resolve model to provider ───────────────────────────────────────

def resolve_model(model_name: str) -> tuple[str, str]:
    """Resolve 'provider:model' or plain model name → (provider, model)."""
    if ":" in model_name:
        parts = model_name.split(":", 1)
        provider = parts[0]
        model = parts[1]
        if provider in PROVIDERS:
            return provider, model
    # Search all providers
    for pname, pinfo in PROVIDERS.items():
        if model_name in pinfo["models"]:
            return pname, model_name
    # Default to mistral
    if MISTRAL_API_KEY:
        return "mistral", model_name
    raise HTTPException(404, f"No provider for model: {model_name}")


# ── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(title="Mascarade Local — Fake Ollama + Mistral P2P")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "providers": list(PROVIDERS.keys()),
        "p2p_peers": len(P2P_PEERS),
    }


# ── Ollama-compatible API ───────────────────────────────────────────

@app.get("/api/tags")
@app.get("/ollama/api/tags")
async def ollama_tags():
    """List all models in Ollama format."""
    models = []
    for pname, pinfo in PROVIDERS.items():
        for model in pinfo["models"]:
            models.append({
                "name": f"{pname}:{model}",
                "model": model,
                "modified_at": "2026-01-01T00:00:00Z",
                "size": 0,
                "digest": "",
                "details": {
                    "parent_model": "",
                    "format": "gguf",
                    "family": pname,
                    "parameter_size": "unknown",
                    "quantization_level": "none",
                },
            })
    return {"models": models}


@app.post("/api/chat")
@app.post("/ollama/api/chat")
async def ollama_chat(request: Request):
    """Ollama-compatible chat endpoint."""
    body = await request.json()
    model_raw = body.get("model", "mistral-large-latest")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    options = body.get("options", {})
    temperature = options.get("temperature", 0.7)
    max_tokens = options.get("num_predict", 4096)

    try:
        provider, model = resolve_model(model_raw)
    except HTTPException:
        # Try P2P
        result = await try_p2p_forward(messages, model_raw, temperature, max_tokens)
        if result:
            return result
        raise

    t0 = time.time()

    if provider == "mistral":
        if stream:
            data = await mistral_chat(messages, model, temperature, max_tokens, stream=True)

            async def _ollama_stream():
                async for chunk in data:
                    try:
                        parsed = json.loads(chunk)
                        content = parsed.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            yield json.dumps({
                                "model": model,
                                "message": {"role": "assistant", "content": content},
                                "done": False,
                            }) + "\n"
                    except json.JSONDecodeError:
                        continue
                yield json.dumps({
                    "model": model,
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                    "total_duration": int((time.time() - t0) * 1e9),
                }) + "\n"

            return StreamingResponse(_ollama_stream(), media_type="application/x-ndjson")

        data = await mistral_chat(messages, model, temperature, max_tokens)
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return {
            "model": model,
            "created_at": "2026-01-01T00:00:00Z",
            "message": {"role": "assistant", "content": content},
            "done": True,
            "total_duration": int((time.time() - t0) * 1e9),
            "prompt_eval_count": usage.get("prompt_tokens", 0),
            "eval_count": usage.get("completion_tokens", 0),
        }

    # For other providers — try P2P
    result = await try_p2p_forward(messages, model_raw, temperature, max_tokens)
    if result:
        return result

    raise HTTPException(503, f"Provider '{provider}' chat not implemented locally. Use P2P.")


@app.post("/api/generate")
@app.post("/ollama/api/generate")
async def ollama_generate(request: Request):
    """Ollama generate endpoint (wraps chat)."""
    body = await request.json()
    prompt = body.get("prompt", "")
    body["messages"] = [{"role": "user", "content": prompt}]
    return await ollama_chat(request)


@app.get("/api/version")
@app.get("/ollama/api/version")
async def ollama_version():
    return {"version": "mascarade-local-0.1.0"}


# ── OpenAI-compatible API (bonus) ───────────────────────────────────

@app.get("/v1/models")
async def openai_models():
    models = []
    for pname, pinfo in PROVIDERS.items():
        for model in pinfo["models"]:
            models.append({
                "id": f"{pname}:{model}",
                "object": "model",
                "owned_by": pname,
            })
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def openai_chat(request: Request):
    """OpenAI-compatible completions (routes to Mistral by default)."""
    body = await request.json()
    model_raw = body.get("model", "mistral-large-latest")
    messages = body.get("messages", [])
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens", 4096)

    provider, model = resolve_model(model_raw)

    if provider == "mistral":
        data = await mistral_chat(messages, model, temperature, max_tokens)
        return data

    raise HTTPException(503, f"Provider '{provider}' not supported in local mode")
