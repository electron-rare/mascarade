"""Fake Ollama API — expose Ollama-compatible endpoints backed by the Mascarade Router.

Any tool or IDE that speaks the Ollama HTTP protocol (``/api/chat``,
``/api/generate``, ``/api/tags``, …) can point at this server and transparently
use every provider registered in Mascarade — including remote P2P peers.

Start standalone:
    FAKE_OLLAMA_ENABLED=true python -m mascarade.ollama_compat

Or mount inside the main server (see ``mount_ollama_compat``).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from mascarade.config import settings

logger = logging.getLogger("mascarade.ollama_compat")

ollama_router = APIRouter(prefix="/ollama", tags=["ollama-compat"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_router(request: Request):
    """Get the Mascarade Router from app state."""
    return request.app.state.router


def _parse_model(model: str) -> tuple[str | None, str | None]:
    """Split a model spec into (provider, model).

    Ollama-native callers send plain model names like ``llama3:8b``.
    Mascarade-aware callers can send ``<provider>:<model>`` to target a
    specific backend.
    """
    if "/" in model:
        # peer_id/provider:model — pass through as-is for P2P
        return None, model
    if model.count(":") == 1:
        left, right = model.split(":", 1)
        # Ollama tags look like ``llama3:8b``, ``qwen2.5:7b`` — the right
        # part is a numeric tag.  Mascarade provider names are alphabetic.
        if left.isalpha() and not right.replace(".", "").replace("-", "").isdigit():
            # e.g. "claude:claude-3-5-sonnet" → provider=claude, model=claude-3-5-sonnet
            return left, right
    # Plain Ollama model name — let the router pick the provider
    return None, model


def _build_messages(body: dict) -> list[dict]:
    """Extract chat messages from an Ollama request body."""
    return body.get("messages", [])


def _build_prompt_messages(body: dict) -> list[dict]:
    """Convert ``/api/generate`` prompt field to messages list."""
    prompt = body.get("prompt", "")
    msgs: list[dict] = []
    if body.get("system"):
        msgs.append({"role": "system", "content": body["system"]})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def _extract_options(body: dict) -> dict[str, Any]:
    opts = body.get("options", {})
    return {
        "temperature": opts.get("temperature", 0.7),
        "max_tokens": opts.get("num_predict", 4096),
    }


# ---------------------------------------------------------------------------
# / — health check (Ollama returns "Ollama is running")
# ---------------------------------------------------------------------------


@ollama_router.get("/")
async def root():
    return PlainTextResponse("Ollama is running")


@ollama_router.get("/api/version")
async def version():
    return {"version": "0.0.0-mascarade"}


# ---------------------------------------------------------------------------
# /api/tags — list models
# ---------------------------------------------------------------------------


@ollama_router.get("/api/tags")
async def list_models(request: Request):
    """Return available models in Ollama ``/api/tags`` format."""
    router = _get_router(request)
    models: list[dict] = []
    for provider_name, provider_models in router.provider_model_map().items():
        for m in provider_models:
            models.append(
                {
                    "name": f"{provider_name}:{m}" if provider_name != "ollama" else m,
                    "model": m,
                    "modified_at": "2026-01-01T00:00:00Z",
                    "size": 0,
                    "digest": "",
                    "details": {
                        "parent_model": "",
                        "format": "gguf",
                        "family": provider_name,
                        "parameter_size": "",
                        "quantization_level": "",
                    },
                }
            )
    return {"models": models}


# ---------------------------------------------------------------------------
# /api/chat — chat completion
# ---------------------------------------------------------------------------


@ollama_router.post("/api/chat")
async def chat_completion(request: Request):
    """Ollama-compatible ``/api/chat`` endpoint."""
    body = await request.json()
    model_spec = body.get("model", "")
    if not model_spec:
        raise HTTPException(400, "model field is required")

    provider, model = _parse_model(model_spec)
    messages = _build_messages(body)
    system = body.get("system") or None
    opts = _extract_options(body)
    stream = body.get("stream", False)

    router = _get_router(request)

    send_kwargs: dict[str, Any] = {
        "messages": messages,
        "system": system,
        **opts,
    }
    if provider:
        send_kwargs["provider"] = provider
        send_kwargs["strategy"] = "specific"

    if stream:
        return StreamingResponse(
            _stream_chat(router, send_kwargs, model_spec),
            media_type="application/x-ndjson",
        )

    # Non-streaming
    response = await router.send(**send_kwargs)
    return JSONResponse(
        {
            "model": model_spec,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message": {
                "role": "assistant",
                "content": response.content,
            },
            "done": True,
            "done_reason": "stop",
            "total_duration": 0,
            "load_duration": 0,
            "prompt_eval_count": response.usage.get("input_tokens", 0),
            "prompt_eval_duration": 0,
            "eval_count": response.usage.get("output_tokens", 0),
            "eval_duration": 0,
        }
    )


async def _stream_chat(router, send_kwargs: dict, model_spec: str):
    """Yield NDJSON chunks in Ollama streaming format."""
    try:
        async for token in router.stream(**send_kwargs):
            chunk = {
                "model": model_spec,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "message": {"role": "assistant", "content": token},
                "done": False,
            }
            yield json.dumps(chunk) + "\n"
    except Exception as exc:
        logger.exception("Ollama compat stream error")
        error_chunk = {
            "model": model_spec,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "error",
            "error": str(exc),
        }
        yield json.dumps(error_chunk) + "\n"
        return

    # Final done chunk
    done_chunk = {
        "model": model_spec,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": "stop",
        "total_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": 0,
        "prompt_eval_duration": 0,
        "eval_count": 0,
        "eval_duration": 0,
    }
    yield json.dumps(done_chunk) + "\n"


# ---------------------------------------------------------------------------
# /api/generate — text completion (legacy)
# ---------------------------------------------------------------------------


@ollama_router.post("/api/generate")
async def generate_completion(request: Request):
    """Ollama-compatible ``/api/generate`` endpoint."""
    body = await request.json()
    model_spec = body.get("model", "")
    if not model_spec:
        raise HTTPException(400, "model field is required")

    provider, model = _parse_model(model_spec)
    messages = _build_prompt_messages(body)
    opts = _extract_options(body)
    stream = body.get("stream", False)

    router = _get_router(request)

    send_kwargs: dict[str, Any] = {
        "messages": messages,
        **opts,
    }
    if provider:
        send_kwargs["provider"] = provider
        send_kwargs["strategy"] = "specific"

    if stream:
        return StreamingResponse(
            _stream_generate(router, send_kwargs, model_spec),
            media_type="application/x-ndjson",
        )

    response = await router.send(**send_kwargs)
    return JSONResponse(
        {
            "model": model_spec,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "response": response.content,
            "done": True,
            "done_reason": "stop",
            "context": [],
            "total_duration": 0,
            "load_duration": 0,
            "prompt_eval_count": response.usage.get("input_tokens", 0),
            "eval_count": response.usage.get("output_tokens", 0),
        }
    )


async def _stream_generate(router, send_kwargs: dict, model_spec: str):
    """Yield NDJSON chunks in Ollama /api/generate streaming format."""
    try:
        async for token in router.stream(**send_kwargs):
            chunk = {
                "model": model_spec,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "response": token,
                "done": False,
            }
            yield json.dumps(chunk) + "\n"
    except Exception as exc:
        logger.exception("Ollama compat generate stream error")
        yield json.dumps({"error": str(exc), "done": True}) + "\n"
        return

    yield json.dumps(
        {
            "model": model_spec,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "response": "",
            "done": True,
            "done_reason": "stop",
        }
    ) + "\n"


# ---------------------------------------------------------------------------
# /api/show — model info (stub)
# ---------------------------------------------------------------------------


@ollama_router.post("/api/show")
async def show_model(request: Request):
    body = await request.json()
    model = body.get("name", body.get("model", "unknown"))
    return JSONResponse(
        {
            "modelfile": f"# Mascarade proxy for {model}",
            "parameters": "",
            "template": "",
            "details": {
                "parent_model": "",
                "format": "mascarade",
                "family": "mascarade",
                "parameter_size": "varies",
                "quantization_level": "N/A",
            },
            "model_info": {},
        }
    )


# ---------------------------------------------------------------------------
# /api/pull, /api/delete — no-ops
# ---------------------------------------------------------------------------


@ollama_router.post("/api/pull")
async def pull_model(request: Request):
    body = await request.json()
    name = body.get("name", "unknown")
    logger.info("Fake Ollama pull requested for %s (no-op)", name)
    return JSONResponse({"status": f"model '{name}' available via mascarade router"})


@ollama_router.delete("/api/delete")
async def delete_model(request: Request):
    return JSONResponse({"status": "no-op (mascarade proxy)"})


# ---------------------------------------------------------------------------
# Mount helper & standalone mode
# ---------------------------------------------------------------------------


def mount_ollama_compat(app: FastAPI) -> None:
    """Include the Ollama-compat router in the main FastAPI app.

    Endpoints become available at:
        http://<host>:<core_port>/ollama/api/chat
        http://<host>:<core_port>/ollama/api/generate
        http://<host>:<core_port>/ollama/api/tags
        etc.

    Point any Ollama client at ``http://<host>:<core_port>/ollama`` as base URL.
    """
    if not getattr(settings, "fake_ollama_enabled", False):
        return

    app.include_router(ollama_router)
    logger.info(
        "Ollama-compat API enabled at /ollama/* (fake_ollama_port=%d for standalone)",
        getattr(settings, "fake_ollama_port", 11434),
    )


def start_standalone():
    """Run the fake Ollama as a standalone uvicorn server on port 11434.

    Useful when you want a drop-in Ollama replacement.
    """
    import uvicorn

    from mascarade.router import Router

    app = FastAPI(title="Mascarade Fake Ollama")
    router = Router()
    app.state.router = router
    app.include_router(ollama_router)

    host = getattr(settings, "fake_ollama_host", "0.0.0.0")
    port = getattr(settings, "fake_ollama_port", 11434)

    logger.info("Starting standalone fake Ollama on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_standalone()
