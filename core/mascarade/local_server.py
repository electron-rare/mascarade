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

import anthropic
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
OPENAI_BASE_URL = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

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
        "models": [
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
        ],
    }
if OPENAI_API_KEY:
    PROVIDERS["openai"] = {
        "base_url": "https://api.openai.com/v1",
        "api_key": OPENAI_API_KEY,
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
    }

logger.info("Providers: %s", list(PROVIDERS.keys()))

PROVIDER_PROBE_TTL_SECONDS = 300.0
PROVIDER_PROBE_CACHE: dict[str, dict] = {}
PROVIDER_ENV_NAMES = {
    "mistral": "MISTRAL_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}
PROVIDER_LABELS = {
    "mistral": "Mistral AI",
    "claude": "Anthropic Claude",
    "openai": "OpenAI",
}
SUPPORTED_LOCAL_CHAT_PROVIDERS = {"mistral", "claude", "openai"}


async def probe_provider_status(provider_name: str, force: bool = False) -> dict:
    """Return a cached readiness snapshot for the provider."""
    now = time.time()
    cached = PROVIDER_PROBE_CACHE.get(provider_name)
    if cached and not force and (now - cached.get("checked_at", 0.0)) < PROVIDER_PROBE_TTL_SECONDS:
        return cached

    status = {
        "name": provider_name,
        "configured": provider_name in PROVIDERS,
        "active": provider_name in PROVIDERS,
        "ready": provider_name in PROVIDERS,
        "error": None,
        "checked_at": now,
    }

    if provider_name in PROVIDERS and provider_name not in SUPPORTED_LOCAL_CHAT_PROVIDERS:
        status["active"] = False
        status["ready"] = False
        status["error"] = "unsupported_local_mode"
    elif provider_name == "mistral" and provider_name in PROVIDERS:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{MISTRAL_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
                )
            if resp.status_code != 200:
                status["active"] = False
                status["ready"] = False
                if resp.status_code == 401:
                    status["error"] = "unauthorized"
                else:
                    status["error"] = f"http_{resp.status_code}"
        except httpx.RequestError as exc:
            status["active"] = False
            status["ready"] = False
            status["error"] = f"request_error:{exc.__class__.__name__}"
    elif provider_name == "openai" and provider_name in PROVIDERS:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{OPENAI_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                )
            if resp.status_code != 200:
                status["active"] = False
                status["ready"] = False
                if resp.status_code == 401:
                    status["error"] = "unauthorized"
                else:
                    status["error"] = f"http_{resp.status_code}"
        except httpx.RequestError as exc:
            status["active"] = False
            status["ready"] = False
            status["error"] = f"request_error:{exc.__class__.__name__}"
    elif provider_name == "claude" and provider_name in PROVIDERS:
        try:
            client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=10.0)
            page = await client.models.list(limit=1)
            if not getattr(page, "data", None):
                status["active"] = False
                status["ready"] = False
                status["error"] = "no_models"
        except anthropic.AuthenticationError:
            status["active"] = False
            status["ready"] = False
            status["error"] = "unauthorized"
        except anthropic.APIConnectionError as exc:
            status["active"] = False
            status["ready"] = False
            status["error"] = f"request_error:{exc.__class__.__name__}"
        except anthropic.APITimeoutError:
            status["active"] = False
            status["ready"] = False
            status["error"] = "timeout"
        except anthropic.APIStatusError as exc:
            status["active"] = False
            status["ready"] = False
            status["error"] = f"http_{exc.status_code}"

    PROVIDER_PROBE_CACHE[provider_name] = status
    return status


async def available_provider_names() -> list[str]:
    names: list[str] = []
    for provider_name in PROVIDERS:
        status = await probe_provider_status(provider_name)
        if status["ready"]:
            names.append(provider_name)
    return names


async def provider_status_payload() -> list[dict]:
    payload: list[dict] = []
    for provider_name, provider_info in PROVIDERS.items():
        probe = await probe_provider_status(provider_name)
        payload.append(
            {
                "name": provider_name,
                "label": PROVIDER_LABELS.get(provider_name, provider_name.title()),
                "configured": probe["configured"],
                "active": probe["active"],
                "fields": [],
                "default_model": provider_info["models"][0] if provider_info["models"] else None,
                "models": provider_info["models"] if probe["ready"] else [],
                "enabled": probe["ready"],
                "auth_mode": "api_key",
                "auth_mode_env": PROVIDER_ENV_NAMES.get(provider_name, f"{provider_name.upper()}_API_KEY"),
                "auth_modes": ["api_key"],
                "classification": "provider-credential",
                "criticality": "feature-required",
                "error": probe["error"],
            }
        )
    return payload


def ollama_result_to_openai_chat_completion(result: dict, requested_model: str) -> dict:
    """Convert an Ollama-style chat response into a minimal OpenAI-compatible payload."""
    message = result.get("message", {}) if isinstance(result, dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    return {
        "id": f"chatcmpl-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.get("model") or requested_model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": result.get("prompt_eval_count", 0),
            "completion_tokens": result.get("eval_count", 0),
            "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
        },
    }


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
        try:
            resp = await client.post(
                f"{MISTRAL_BASE_URL}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Mistral upstream timed out") from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            raise HTTPException(
                502,
                f"Mistral upstream returned {exc.response.status_code}: {detail[:400]}",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Mistral upstream request failed: {exc}") from exc
        finally:
            await client.aclose()
    else:
        # Streaming
        async def _stream():
            try:
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
            except httpx.TimeoutException as exc:
                raise HTTPException(504, "Mistral upstream timed out") from exc
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text.strip() or exc.response.reason_phrase
                raise HTTPException(
                    502,
                    f"Mistral upstream returned {exc.response.status_code}: {detail[:400]}",
                ) from exc
            except httpx.RequestError as exc:
                raise HTTPException(502, f"Mistral upstream request failed: {exc}") from exc
            finally:
                await client.aclose()

        return _stream()


async def openai_provider_chat(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    stream: bool = False,
) -> dict | AsyncIterator[str]:
    """Call OpenAI Chat Completions via plain HTTP."""
    if not OPENAI_API_KEY:
        raise HTTPException(503, "OPENAI_API_KEY not configured")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    client = httpx.AsyncClient(timeout=180.0)

    if not stream:
        try:
            resp = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "OpenAI upstream timed out") from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            raise HTTPException(
                502,
                f"OpenAI upstream returned {exc.response.status_code}: {detail[:400]}",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, f"OpenAI upstream request failed: {exc}") from exc
        finally:
            await client.aclose()
    else:
        async def _stream():
            try:
                async with client.stream(
                    "POST",
                    f"{OPENAI_BASE_URL}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                ) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_text():
                        yield chunk
            except httpx.TimeoutException as exc:
                raise HTTPException(504, "OpenAI upstream timed out") from exc
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text.strip() or exc.response.reason_phrase
                raise HTTPException(
                    502,
                    f"OpenAI upstream returned {exc.response.status_code}: {detail[:400]}",
                ) from exc
            except httpx.RequestError as exc:
                raise HTTPException(502, f"OpenAI upstream request failed: {exc}") from exc
            finally:
                await client.aclose()

        return _stream()


async def claude_chat(
    messages: list[dict],
    model: str = "claude-sonnet-4-6",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> dict:
    """Call Anthropic Claude via the installed SDK."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    system_parts: list[str] = []
    anthropic_messages: list[dict] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            system_parts.append(str(content))
            continue
        anthropic_role = "assistant" if role == "assistant" else "user"
        anthropic_messages.append({"role": anthropic_role, "content": str(content)})

    if not anthropic_messages:
        anthropic_messages = [{"role": "user", "content": "Continue."}]

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)
    try:
        response = await client.messages.create(
            model=model,
            system="\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response.content[0].text if response.content else ""
        usage = response.usage
        return {
            "model": model,
            "content": content,
            "usage": {
                "prompt_tokens": usage.input_tokens if usage else 0,
                "completion_tokens": usage.output_tokens if usage else 0,
            },
        }
    except anthropic.AuthenticationError as exc:
        raise HTTPException(502, f"Claude upstream returned 401: {str(exc)[:400]}") from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(429, f"Claude upstream rate-limited: {str(exc)[:400]}") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(502, f"Claude upstream request failed: {str(exc)[:400]}") from exc
    except anthropic.APITimeoutError as exc:
        raise HTTPException(504, "Claude upstream timed out") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(
            502,
            f"Claude upstream returned {exc.status_code}: {str(exc)[:400]}",
        ) from exc


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
    statuses = {
        status["name"]: status
        for status in await provider_status_payload()
    }
    return {
        "status": "ok",
        "providers": [name for name, status in statuses.items() if status["active"]],
        "configured_providers": list(PROVIDERS.keys()),
        "provider_status": statuses,
        "p2p_peers": len(P2P_PEERS),
    }


@app.get("/providers/status")
@app.get("/v1/providers/status")
async def providers_status():
    return {"providers": await provider_status_payload()}


# ── Ollama-compatible API ───────────────────────────────────────────

@app.get("/api/tags")
@app.get("/ollama/api/tags")
async def ollama_tags():
    """List all models in Ollama format."""
    models = []
    for pname in await available_provider_names():
        pinfo = PROVIDERS[pname]
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

    if provider == "openai":
        data = await openai_provider_chat(messages, model, temperature, max_tokens)
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

    if provider == "claude":
        data = await claude_chat(messages, model, temperature, max_tokens)
        usage = data.get("usage", {})
        return {
            "model": data.get("model", model),
            "created_at": "2026-01-01T00:00:00Z",
            "message": {"role": "assistant", "content": data.get("content", "")},
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
    for pname in await available_provider_names():
        pinfo = PROVIDERS[pname]
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

    try:
        provider, model = resolve_model(model_raw)
    except HTTPException:
        result = await try_p2p_forward(messages, model_raw, temperature, max_tokens)
        if result:
            return ollama_result_to_openai_chat_completion(result, model_raw)
        raise

    if provider == "mistral":
        try:
            data = await mistral_chat(messages, model, temperature, max_tokens)
            return data
        except HTTPException:
            result = await try_p2p_forward(messages, model_raw, temperature, max_tokens)
            if result:
                return ollama_result_to_openai_chat_completion(result, model_raw)
            raise

    if provider == "openai":
        return await openai_provider_chat(messages, model, temperature, max_tokens)

    if provider == "claude":
        data = await claude_chat(messages, model, temperature, max_tokens)
        return {
            "id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": data.get("model", model),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": data.get("content", ""),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": (
                    data.get("usage", {}).get("prompt_tokens", 0)
                    + data.get("usage", {}).get("completion_tokens", 0)
                ),
            },
        }

    result = await try_p2p_forward(messages, model_raw, temperature, max_tokens)
    if result:
        return ollama_result_to_openai_chat_completion(result, model_raw)

    raise HTTPException(503, f"Provider '{provider}' not supported in local mode")
