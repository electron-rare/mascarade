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

    # ViewerSettings
    if "viewersettings" in query_lower:
        return {
            "data": {
                "viewerSettings": {
                    "final": json.dumps({
                        "cody.enabled": True,
                        "cody.autocomplete.enabled": True,
                        "cody.chat.enabled": True,
                        "cody.serverEndpoint": "",
                    }),
                }
            }
        }

    # Repositories
    if "repositories" in query_lower or "repository" in query_lower:
        return {
            "data": {
                "repositories": {
                    "nodes": [],
                    "totalCount": 0,
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }

    # CodeSearchEnabled
    if "codesearchenabled" in query_lower:
        return {
            "data": {
                "site": {
                    "isCodyEnabled": True,
                }
            }
        }

    # SiteProductVersion
    if "siteproductversion" in query_lower or "productversion" in query_lower:
        return {
            "data": {
                "site": {
                    "productVersion": "6.0.0",
                    "hasCodeIntelligence": True,
                }
            }
        }

    # ViewerPrompts / Prompts
    if "viewerprompts" in query_lower or "prompttags" in query_lower:
        return {
            "data": {
                "prompts": {
                    "nodes": [],
                    "totalCount": 0,
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
                "promptTags": [],
            }
        }

    # ViewerBuiltinPrompts
    if "viewerbuiltinprompts" in query_lower or "builtinprompts" in query_lower:
        return {
            "data": {
                "builtinPrompts": [],
            }
        }

    # RecordTelemetryEvents — just accept silently
    if "recordtelemetryevents" in query_lower or "telemetry" in query_lower:
        return {"data": {"telemetry": {"recordEvents": {"alwaysNil": None}}}}

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

    # Cody appends ?OperationName to the URL — use it as a hint
    url_query = str(request.url.query).lower()
    combined = f"{url_query} {query}"

    result = _handle_graphql(combined, variables)
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
            yield "event: done\ndata: {}\n\n"

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


@cody_router.get("/prompts")
@cody_router.get("/.api/prompts")
async def prompts(request: Request):
    """Prompt library — reusable prompt templates for Cody."""
    _get_router(request)
    registry = getattr(request.app.state, "registry", None)

    prompt_list = []

    # Build prompts from registered agents
    if registry:
        for agent in registry.list():
            prompt_list.append({
                "id": f"mascarade-{agent.name}",
                "name": agent.name.replace("-", " ").title(),
                "description": agent.description,
                "prompt": agent.system_prompt[:200],
                "mode": "chat",
                "model": f"{agent.preferred_provider or 'ollama'}/{agent.preferred_model or 'devstral'}",
                "tags": [getattr(agent, "category", None) or "general", getattr(agent, "routing_policy", "auto")],
                "builtin": True,
            })

    # Add curated prompts
    _CURATED = [
        {
            "id": "explain-code",
            "name": "Explain Code",
            "description": "Explain what the selected code does in plain language",
            "prompt": "Explain the following code step by step. Be concise and focus on the logic, not obvious syntax.\n\n```\n{selection}\n```",
            "mode": "chat",
            "tags": ["code", "explain"],
        },
        {
            "id": "fix-bug",
            "name": "Fix Bug",
            "description": "Find and fix bugs in the selected code",
            "prompt": "Find bugs in the following code. For each bug: explain what's wrong, why it's a problem, and provide the fix.\n\n```\n{selection}\n```",
            "mode": "chat",
            "tags": ["code", "debug"],
        },
        {
            "id": "write-tests",
            "name": "Write Tests",
            "description": "Generate unit tests for the selected code",
            "prompt": "Write comprehensive unit tests for the following code. Use pytest. Cover edge cases and error paths.\n\n```\n{selection}\n```",
            "mode": "chat",
            "tags": ["code", "test"],
        },
        {
            "id": "refactor",
            "name": "Refactor",
            "description": "Refactor the selected code for clarity and performance",
            "prompt": "Refactor the following code. Improve readability, reduce complexity, and follow best practices. Explain each change.\n\n```\n{selection}\n```",
            "mode": "chat",
            "tags": ["code", "refactor"],
        },
        {
            "id": "document",
            "name": "Document",
            "description": "Add docstrings and comments to the selected code",
            "prompt": "Add clear docstrings and inline comments to the following code. Use the project's style (Google/NumPy for Python, JSDoc for TS).\n\n```\n{selection}\n```",
            "mode": "chat",
            "tags": ["code", "docs"],
        },
        {
            "id": "translate-lang",
            "name": "Translate Code",
            "description": "Translate code from one language to another",
            "prompt": "Translate the following code to {language}. Preserve logic and use idiomatic patterns in the target language.\n\n```\n{selection}\n```",
            "mode": "chat",
            "tags": ["code", "translate"],
        },
        {
            "id": "review-security",
            "name": "Security Review",
            "description": "Check code for security vulnerabilities (OWASP)",
            "prompt": "Perform a security review of the following code. Check for: injection, XSS, SSRF, auth bypass, secrets exposure, and other OWASP Top 10 issues.\n\n```\n{selection}\n```",
            "mode": "chat",
            "tags": ["code", "security"],
        },
        {
            "id": "pcb-review",
            "name": "PCB Design Review",
            "description": "Review KiCad PCB design for DRC, EMC, and manufacturing issues",
            "prompt": "Review this PCB design/schematic for: DRC violations, EMC issues, thermal concerns, manufacturing constraints (JLCPCB/PCBWay), and IPC compliance.\n\n{selection}",
            "mode": "chat",
            "model": "ollama/mascarade-kicad",
            "tags": ["domain", "electronics"],
        },
        {
            "id": "spice-sim",
            "name": "SPICE Simulation",
            "description": "Generate or debug SPICE netlists",
            "prompt": "Generate a SPICE netlist for the following circuit description. Include AC/DC/transient analysis directives.\n\n{selection}",
            "mode": "chat",
            "model": "ollama/mascarade-spice",
            "tags": ["domain", "electronics"],
        },
        {
            "id": "summarize-fr",
            "name": "Résumer (FR)",
            "description": "Résume le texte en bullet points concis",
            "prompt": "Résume le texte suivant en bullet points clairs et concis. Conserve les informations clés.\n\n{selection}",
            "mode": "chat",
            "tags": ["text", "french"],
        },
    ]

    prompt_list.extend(_CURATED)

    return {
        "prompts": prompt_list,
        "totalCount": len(prompt_list),
    }


@cody_router.get("/agents")
@cody_router.get("/v1/agents")
async def list_agents(request: Request):
    """List all registered agents."""
    registry = getattr(request.app.state, "registry", None)
    if not registry:
        return []
    agents = []
    for agent in registry.list():
        agents.append({
            "name": agent.name,
            "description": agent.description,
            "strategy": str(getattr(agent, "strategy", "best")),
            "provider": getattr(agent, "preferred_provider", None),
            "model": getattr(agent, "preferred_model", None),
            "temperature": getattr(agent, "temperature", 0.7),
            "category": getattr(agent, "category", None),
            "routing_policy": getattr(agent, "routing_policy", "auto"),
        })
    return agents


@cody_router.get("/agents/{name}")
async def get_agent(name: str, request: Request):
    """Get a single agent by name."""
    registry = getattr(request.app.state, "registry", None)
    if not registry:
        raise HTTPException(status_code=404, detail="No registry")
    try:
        agent = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return {
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "strategy": str(getattr(agent, "strategy", "best")),
        "preferred_provider": getattr(agent, "preferred_provider", None),
        "preferred_model": getattr(agent, "preferred_model", None),
        "temperature": getattr(agent, "temperature", 0.7),
        "max_tokens": getattr(agent, "max_tokens", 4096),
        "category": getattr(agent, "category", None),
        "routing_policy": getattr(agent, "routing_policy", "auto"),
    }


@cody_router.post("/agents/{name}/run")
async def run_agent(name: str, request: Request):
    """Run an agent with messages."""
    registry = getattr(request.app.state, "registry", None)
    router = _get_router(request)
    if not registry or not router:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        agent = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    prompt = messages[-1].get("content", "")
    context = messages[:-1] if len(messages) > 1 else None
    try:
        response = await agent.run(prompt, router=router, context=context)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@cody_router.post("/agents")
async def create_agent(request: Request):
    """Create a new agent."""
    from mascarade.agents.base import Agent as AgentClass
    from mascarade.router.router import Strategy as StrategyEnum

    registry = getattr(request.app.state, "registry", None)
    if not registry:
        raise HTTPException(status_code=503, detail="No registry")

    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    try:
        strategy = StrategyEnum(body.get("strategy", "best"))
    except ValueError:
        strategy = StrategyEnum.BEST

    agent = AgentClass(
        name=name,
        description=body.get("description", ""),
        system_prompt=body.get("system_prompt", ""),
        preferred_provider=body.get("preferred_provider"),
        preferred_model=body.get("preferred_model"),
        strategy=strategy,
        routing_policy=body.get("routing_policy", "auto"),
        temperature=body.get("temperature", 0.7),
        max_tokens=body.get("max_tokens", 4096),
    )
    registry.register(agent)
    try:
        registry.save()
    except Exception:
        pass
    return {"name": agent.name, "status": "created"}


@cody_router.post("/prompts/{name}/run")
async def run_prompt(name: str, request: Request):
    """Run a prompt/agent by name — used by ops copilote."""
    registry = getattr(request.app.state, "registry", None)
    router = _get_router(request)
    if not registry or not router:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Try agent first, then fall back to agent-zero with the prompt name as context
    try:
        agent = registry.get(name)
    except KeyError:
        # Fall back to agent-zero
        try:
            agent = registry.get("agent-zero")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    body = await request.json()
    messages = body.get("messages", [])
    prompt = body.get("prompt", "")
    if not messages and prompt:
        messages = [{"role": "user", "content": prompt}]
    if not messages:
        raise HTTPException(status_code=400, detail="messages or prompt required")

    prompt_text = messages[-1].get("content", "")
    context = messages[:-1] if len(messages) > 1 else None
    try:
        response = await agent.run(prompt_text, router=router, context=context)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "agent": agent.name,
    }


@cody_router.post("/send")
async def send_message(request: Request):
    """Direct send to the router — used by ops copilote."""
    router = _get_router(request)
    if not router:
        raise HTTPException(status_code=503, detail="Router not available")

    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    try:
        response = await router.send(
            messages,
            provider=body.get("provider"),
            model=body.get("model"),
            system=body.get("system"),
            temperature=body.get("temperature", 0.7),
            max_tokens=body.get("max_tokens", 4096),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@cody_router.get("/healthz")
async def healthz():
    """Kubernetes-style health check (Cody expects this)."""
    return {"status": "ok"}


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


# ---------------------------------------------------------------------------
# Ops console compatibility routes
# ---------------------------------------------------------------------------

@cody_router.get("/v1/api/v1/agents")
async def ops_list_agents(request: Request):
    agents = await list_agents(request)
    return {"agents": agents}

@cody_router.get("/v1/api/v1/agents/{name}")
async def ops_get_agent(name: str, request: Request):
    return await get_agent(name, request)

@cody_router.get("/v1/api/providers")
async def ops_providers(request: Request):
    h = await health_check(request)
    return [{"id": p, "configured": True} for p in h.get("providers", [])]

@cody_router.get("/v1/api/providers/status")
async def ops_providers_status(request: Request):
    h = await health_check(request)
    return {"providers": h.get("providers", []), "status": "ok"}

@cody_router.get("/v1/api/cli-agents/status")
async def ops_cli_status():
    return {"agents": [], "status": "ok"}

@cody_router.post("/v1/api/cli-agents/run")
async def ops_cli_run():
    return {"status": "not_implemented"}
