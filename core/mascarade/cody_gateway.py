"""Cody Gateway — minimal Sourcegraph-compatible proxy for Mascarade.

Makes the Cody VSCode extension believe it's talking to a real Sourcegraph
instance, while routing all LLM requests through the Mascarade router.

Endpoints:
  GET  /.api/client-config          — client configuration (models, providers)
  POST /.api/completions/stream     — autocomplete (SSE streaming)
  POST /.api/chat/completions       — chat (OpenAI-compatible)
  GET  /.auth/callback              — fake OAuth callback
  POST /.api/graphql                — minimal GraphQL for user/site info
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger("mascarade.cody_gateway")

cody_router = APIRouter(tags=["cody-gateway"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_router(request: Request):
    return getattr(request.app.state, "router", None)


def _build_model_list(request: Request) -> list[dict]:
    """Build Sourcegraph-compatible model list from Mascarade providers."""
    router = _get_router(request)
    if not router:
        return []

    models = []
    model_map = router.provider_model_map()
    for provider_name, provider_models in model_map.items():
        for m in provider_models:
            model_id = f"{provider_name}/{m}" if provider_name != "ollama" else f"ollama/{m}"
            models.append({
                "modelRef": model_id,
                "displayName": f"{m} ({provider_name})",
                "modelName": m,
                "capabilities": ["autocomplete", "chat"],
                "category": "balanced",
                "status": "stable",
                "tier": "free",
                "contextWindow": {
                    "maxInputTokens": 32000,
                    "maxOutputTokens": 4096,
                },
                "provider": provider_name,
                "serverSideConfig": {
                    "type": "openaicompatible",
                },
            })
    return models


# ---------------------------------------------------------------------------
# GraphQL — minimal subset Cody needs
# ---------------------------------------------------------------------------

_GRAPHQL_HANDLERS: dict[str, Any] = {}


def _handle_graphql(query: str, variables: dict | None = None) -> dict:
    """Route GraphQL queries to handlers."""
    query_lower = query.lower().strip()

    # CurrentUser query
    if "currentuser" in query_lower or "viewer" in query_lower:
        return {
            "data": {
                "currentUser": {
                    "id": "VXNlcjox",
                    "username": "mascarade",
                    "displayName": "Mascarade User",
                    "email": "mascarade@saillant.cc",
                    "siteAdmin": True,
                    "hasVerifiedEmail": True,
                    "organizations": {"nodes": []},
                    "session": {"canSignOut": False},
                    "viewerCanAdminister": True,
                    "codyProEnabled": True,
                    "completionsQuotaExceeded": False,
                }
            }
        }

    # Site config / version
    if "site" in query_lower and ("version" in query_lower or "configuration" in query_lower):
        return {
            "data": {
                "site": {
                    "productVersion": "6.0.0",
                    "productSubscription": {
                        "license": {
                            "isValid": True,
                            "info": {
                                "tags": ["plan:enterprise-1"],
                                "expiresAt": "2099-12-31T23:59:59Z",
                            },
                        }
                    },
                    "codyLLMConfiguration": {
                        "provider": "sourcegraph",
                        "chatModel": "ollama/devstral",
                        "completionModel": "ollama/devstral",
                        "fastChatModel": "ollama/qwen3.5:4b",
                    },
                    "needsRepositoryConfiguration": False,
                    "freeUsersExceeded": False,
                    "authProviders": {"nodes": []},
                    "sendsEmailVerificationEmails": False,
                    "allowSignup": False,
                    "updateCheck": {"pending": False, "updateVersionAvailable": None},
                }
            }
        }

    # CodyLLMConfiguration
    if "codyllmconfiguration" in query_lower or "cody" in query_lower:
        return {
            "data": {
                "site": {
                    "codyLLMConfiguration": {
                        "provider": "sourcegraph",
                        "chatModel": "ollama/devstral",
                        "completionModel": "ollama/devstral",
                        "fastChatModel": "ollama/qwen3.5:4b",
                    }
                },
                "currentUser": {
                    "codyProEnabled": True,
                    "completionsQuotaExceeded": False,
                },
            }
        }

    # Evaluatefeatureflags / feature flags
    if "featureflag" in query_lower or "evaluatefeatureflags" in query_lower:
        return {
            "data": {
                "evaluateFeatureFlags": {
                    "codyAutocomplete": True,
                    "codyChat": True,
                    "codyPro": True,
                }
            }
        }

    # Catch-all: return empty data
    logger.debug("Unhandled GraphQL query: %s", query[:100])
    return {"data": {}}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@cody_router.post("/.api/graphql")
async def graphql(request: Request):
    """Minimal GraphQL endpoint for Cody's user/site queries."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    query = body.get("query", "")
    variables = body.get("variables", {})
    result = _handle_graphql(query, variables)
    return JSONResponse(result)


@cody_router.get("/.api/client-config")
async def client_config(request: Request):
    """Return Cody client configuration with available models."""
    models = _build_model_list(request)
    return {
        "chatModel": "ollama/devstral",
        "chatModelMaxTokens": 32000,
        "completionModel": "ollama/devstral",
        "completionModelMaxTokens": 4096,
        "fastChatModel": "ollama/qwen3.5:4b",
        "fastChatModelMaxTokens": 4096,
        "provider": "sourcegraph",
        "codyEnabled": True,
        "modelsAPIEnabled": True,
        "models": models,
    }


@cody_router.get("/.api/modelconfig/supported-models.json")
async def supported_models(request: Request):
    """Return supported models list."""
    models = _build_model_list(request)
    return {
        "schemaVersion": "1.0",
        "revision": "mascarade-1",
        "providers": [],
        "models": models,
        "defaultModels": {
            "chat": "ollama/devstral",
            "fastChat": "ollama/qwen3.5:4b",
            "codeCompletion": "ollama/devstral",
        },
    }


@cody_router.post("/.api/completions/stream")
async def completions_stream(request: Request):
    """Autocomplete endpoint — SSE streaming format."""
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "ollama/devstral")
    max_tokens = body.get("maxTokensToSample", 256)
    temperature = body.get("temperature", 0.2)

    # Convert Sourcegraph model ref to Mascarade format
    # "ollama/devstral" -> provider=ollama, model=devstral
    provider_hint = None
    model_name = model
    if "/" in model:
        parts = model.split("/", 1)
        provider_hint = parts[0]
        model_name = parts[1]

    # Convert Cody message format to standard
    chat_messages = []
    for msg in messages:
        speaker = msg.get("speaker", "human")
        role = "user" if speaker == "human" else "assistant"
        text = msg.get("text", "")
        if text:
            chat_messages.append({"role": role, "content": text})

    if not chat_messages:
        chat_messages = [{"role": "user", "content": ""}]

    router = _get_router(request)
    if not router:
        raise HTTPException(status_code=503, detail="Router not available")

    async def generate():
        try:
            response = await router.send(
                chat_messages,
                provider=provider_hint,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.content or ""

            # SSE format Cody expects
            yield f"event: completion\ndata: {json.dumps({'completion': content})}\n\n"
            yield f"event: done\ndata: {{}}\n\n"

        except Exception as exc:
            logger.error("Completions error: %s", exc)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
        },
    )


@cody_router.post("/.api/chat/completions")
async def chat_completions(request: Request):
    """Chat completions — OpenAI-compatible format."""
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "ollama/devstral")
    max_tokens = body.get("max_tokens", body.get("maxTokensToSample", 4096))
    temperature = body.get("temperature", 0.7)
    stream = body.get("stream", False)

    provider_hint = None
    model_name = model
    if "/" in model:
        parts = model.split("/", 1)
        provider_hint = parts[0]
        model_name = parts[1]

    # Normalize messages (Cody sometimes uses "speaker" format)
    chat_messages = []
    for msg in messages:
        if "speaker" in msg:
            role = "user" if msg["speaker"] == "human" else "assistant"
            chat_messages.append({"role": role, "content": msg.get("text", "")})
        else:
            chat_messages.append(msg)

    router = _get_router(request)
    if not router:
        raise HTTPException(status_code=503, detail="Router not available")

    if stream:
        async def generate():
            try:
                async for chunk in router.stream(
                    chat_messages,
                    provider=provider_hint,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    data = {
                        "choices": [{
                            "delta": {"content": chunk},
                            "index": 0,
                            "finish_reason": None,
                        }]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as exc:
                logger.error("Stream error: %s", exc)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    # Non-streaming
    try:
        response = await router.send(
            chat_messages,
            provider=provider_hint,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response.content,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": response.usage.get("input_tokens", 0),
            "completion_tokens": response.usage.get("output_tokens", 0),
            "total_tokens": sum(response.usage.values()),
        },
    }


@cody_router.get("/.auth/callback")
async def auth_callback(code: str = "", state: str = ""):
    """Fake OAuth callback — always succeeds."""
    return JSONResponse({
        "type": "callback",
        "payload": {
            "accessToken": "sgp_mascarade_" + uuid.uuid4().hex[:16],
            "user": {"username": "mascarade"},
        },
    })


@cody_router.get("/.auth/authorize")
async def auth_authorize(response_type: str = "", client_id: str = "", state: str = ""):
    """Fake OAuth authorize — redirect with token."""
    token = "sgp_mascarade_" + uuid.uuid4().hex[:16]
    # Redirect back to callback with code
    from fastapi.responses import RedirectResponse
    callback_url = f"/.auth/callback?code={token}&state={state}"
    return RedirectResponse(url=callback_url)


@cody_router.get("/.well-known/openid-configuration")
async def openid_config(request: Request):
    """Fake OIDC discovery."""
    base = str(request.base_url).rstrip("/")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/.auth/authorize",
        "token_endpoint": f"{base}/.auth/callback",
        "userinfo_endpoint": f"{base}/.api/graphql",
    }


# ---------------------------------------------------------------------------
# Mount helper
# ---------------------------------------------------------------------------

def mount_cody_gateway(app: FastAPI) -> None:
    """Mount Cody Gateway routes on the main app."""
    app.include_router(cody_router)
    logger.info("Cody Gateway mounted (/.api/completions/stream, /.api/chat/completions, /.api/graphql)")
