"""Chat endpoints - OpenAI-compatible and Ollama-compatible shims."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from mascarade.config import settings
from mascarade.models.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    OllamaChatRequest,
    OllamaGenerateRequest,
)
from mascarade.project_scope import normalize_scope
from mascarade.router.router import Strategy

router = APIRouter(tags=["chat"], prefix="/v1")
ollama_router = APIRouter(tags=["chat"])


SUPPORTED_PROVIDER_PREFIXES = frozenset(
    [
        "apple-coreml",
        "ollama",
        "openai",
        "claude",
        "anthropic",
        "mistral",
        "google",
        "mlx-lm",
        "huggingface",
    ]
)

PROVIDER_PREFIX_ALIASES = {
    "anthropic": "claude",
}

AUTO_ROUTE_MODEL_POLICIES = {
    "auto": "auto",
    "auto:strong": "strong",
    "auto:cheap": "cheap",
    "auto:fast": "fast",
}


def _default_project_id() -> str:
    return settings.mascarade_project_id.strip() or "default"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_model_name(model: str | None) -> str | None:
    if model is None:
        return None
    normalized = model.strip()
    return normalized or None


def _normalize_strategy(strategy: str | Strategy | None) -> Strategy | None:
    if strategy is None:
        return None
    if isinstance(strategy, Strategy):
        return strategy
    try:
        return Strategy(str(strategy))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported strategy '{strategy}'.") from exc


def _normalize_routing_policy(routing_policy: str | None) -> str | None:
    if routing_policy is None:
        return None
    normalized = routing_policy.strip().lower()
    if not normalized:
        return None
    if normalized not in {"auto", "strong", "cheap", "fast"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported routing_policy '{routing_policy}'.",
        )
    return normalized


def _provider_model_map(router_instance: Any) -> dict[str, list[str]]:
    provider_model_map = getattr(router_instance, "provider_model_map", None)
    if not callable(provider_model_map):
        return {}
    try:
        mapping = provider_model_map()
    except Exception:
        return {}
    if not isinstance(mapping, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for provider, models in mapping.items():
        if not isinstance(provider, str):
            continue
        if not isinstance(models, list):
            continue
        normalized[provider] = [model for model in models if isinstance(model, str) and model.strip()]
    return normalized


def _infer_provider_for_model(model: str, router_instance: Any) -> str | None:
    provider_model_map = _provider_model_map(router_instance)
    if not provider_model_map:
        return None
    owners = [
        provider
        for provider, models in provider_model_map.items()
        if model in models
    ]
    if not owners:
        return None
    if len(owners) == 1:
        return owners[0]
    default_provider = settings.default_provider.strip()
    if default_provider and default_provider in owners:
        return default_provider
    return None


def _parse_model_string(
    model: str | None,
    router_instance: Any,
) -> tuple[str | None, str | None, str]:
    """Parse a model string into (provider, model_name, display_model)."""
    normalized = _normalize_model_name(model)
    if normalized is None:
        display_model = _normalize_model_name(settings.default_model) or "auto"
        return None, None, display_model
    if normalized in AUTO_ROUTE_MODEL_POLICIES:
        return None, None, normalized

    supported = getattr(router_instance, "supported_provider_names", None)
    if supported is None:
        supported = list(SUPPORTED_PROVIDER_PREFIXES)
    available = getattr(router_instance, "available_providers", [])
    if available:
        supported = list(set(supported) | set(available))

    if ":" in normalized:
        for prefix in supported:
            if normalized.startswith(prefix + ":"):
                model_name = normalized[len(prefix) + 1 :]
                return PROVIDER_PREFIX_ALIASES.get(prefix, prefix), model_name, normalized
        inferred_provider = _infer_provider_for_model(normalized, router_instance)
        if inferred_provider is not None:
            return inferred_provider, normalized, normalized
        prefix = normalized.split(":", 1)[0]
        if prefix not in supported:
            raise ValueError(f"Unsupported model prefix '{prefix}'.")
        model_name = normalized[len(prefix) + 1 :]
        return PROVIDER_PREFIX_ALIASES.get(prefix, prefix), model_name, normalized

    inferred_provider = _infer_provider_for_model(normalized, router_instance)
    if inferred_provider is not None:
        return inferred_provider, normalized, normalized
    return None, normalized, normalized


def _message_to_dict(message: Any) -> dict[str, Any]:
    content = getattr(message, "content", None)
    return {
        "role": getattr(message, "role"),
        "content": content or "",
        **({"name": getattr(message, "name")} if getattr(message, "name", None) else {}),
        **(
            {"tool_call_id": getattr(message, "tool_call_id")}
            if getattr(message, "tool_call_id", None)
            else {}
        ),
    }


def _split_messages(messages: list[Any]) -> tuple[list[dict[str, Any]], str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    all_messages: list[dict[str, Any]] = []
    non_system_messages: list[dict[str, Any]] = []

    for message in messages:
        msg_dict = _message_to_dict(message)
        all_messages.append(msg_dict)
        if msg_dict["role"] == "system":
            system_parts.append(str(msg_dict["content"] or ""))
        else:
            non_system_messages.append(msg_dict)

    system_prompt = "\n".join(system_parts) if system_parts else None
    effective_messages = non_system_messages if system_parts else all_messages
    return effective_messages, system_prompt, all_messages


def _format_response_model(provider: str | None, model: str | None, *, fallback: str) -> str:
    if model is None or not str(model).strip():
        return fallback
    normalized_model = str(model).strip()
    normalized_provider = (provider or "").strip()
    if not normalized_provider or ":" in normalized_provider:
        return normalized_model
    if normalized_model.startswith(normalized_provider + ":"):
        return normalized_model
    return f"{normalized_provider}:{normalized_model}"


def _resolve_requested_routing(
    *,
    router_instance: Any,
    model: str | None,
    strategy: str | Strategy | None,
    routing_policy: str | None,
) -> tuple[Strategy, str | None, str | None, str | None, str]:
    requested_strategy = _normalize_strategy(strategy)
    normalized_policy = _normalize_routing_policy(routing_policy)
    try:
        provider, model_name, display_model = _parse_model_string(model, router_instance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    available = getattr(router_instance, "available_providers", [])
    auto_policy = AUTO_ROUTE_MODEL_POLICIES.get(display_model)
    if auto_policy is not None:
        return Strategy.ROUTELLM, auto_policy, None, None, display_model

    if provider is not None:
        if available and provider not in available:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": f"Provider '{provider}' is not configured or unavailable.",
                    "providers": list(available),
                },
            )
        return Strategy.SPECIFIC, normalized_policy, provider, model_name, display_model

    if requested_strategy == Strategy.SPECIFIC:
        raise HTTPException(
            status_code=400,
            detail="strategy 'specific' requires a provider-prefixed or uniquely owned model.",
        )

    if requested_strategy is not None:
        return requested_strategy, normalized_policy, None, model_name, display_model

    if normalized_policy is not None:
        return Strategy.ROUTELLM, normalized_policy, None, model_name, display_model

    default_provider = settings.default_provider.strip()
    default_model = _normalize_model_name(settings.default_model)
    if model_name is None:
        if available and default_provider and default_provider in available:
            return Strategy.SPECIFIC, None, default_provider, default_model, default_model or display_model
        if available:
            return Strategy.SPECIFIC, None, available[0], None, display_model
        return Strategy.BEST, None, None, None, display_model

    if available and default_provider and default_provider in available:
        return Strategy.SPECIFIC, None, default_provider, model_name, display_model
    if available:
        return Strategy.SPECIFIC, None, available[0], model_name, display_model
    return Strategy.BEST, None, None, model_name, display_model


def _response_format_from_openai(request_body: ChatCompletionRequest) -> dict[str, Any] | None:
    if request_body.response_format is None:
        return None
    return {"type": request_body.response_format.type}


def _response_format_from_ollama(fmt: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if fmt is None:
        return None
    if isinstance(fmt, str):
        if fmt == "json":
            return {"type": "json_object"}
        return {"type": "text"}
    return fmt


def _ollama_generation_params(options: dict[str, Any] | None) -> tuple[float, int]:
    options = options or {}
    temperature = options.get("temperature", 0.7)
    max_tokens = options.get("num_predict", 4096)
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.7
    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens = 4096
    return temperature, max(1, max_tokens)


def _ollama_chat_payload(
    *,
    model: str,
    content: str,
    prompt_tokens: int,
    completion_tokens: int,
    done: bool,
) -> dict[str, Any]:
    return {
        "model": model,
        "created_at": _utc_now_iso(),
        "message": {
            "role": "assistant",
            "content": content,
        },
        "done": done,
        "done_reason": "stop" if done else None,
        "prompt_eval_count": prompt_tokens,
        "eval_count": completion_tokens,
        "total_duration": 0,
        "load_duration": 0,
    }


def _ollama_generate_payload(
    *,
    model: str,
    content: str,
    prompt_tokens: int,
    completion_tokens: int,
    done: bool,
) -> dict[str, Any]:
    return {
        "model": model,
        "created_at": _utc_now_iso(),
        "response": content,
        "done": done,
        "done_reason": "stop" if done else None,
        "prompt_eval_count": prompt_tokens,
        "eval_count": completion_tokens,
        "total_duration": 0,
        "load_duration": 0,
    }


def _ollama_tag_entry(model: str, *, provider: str, parent_model: str | None = None) -> dict[str, Any]:
    return {
        "name": model,
        "model": model,
        "modified_at": _utc_now_iso(),
        "size": 0,
        "digest": f"mascarade::{provider}::{model}",
        "details": {
            "parent_model": parent_model or "",
            "format": "router",
            "family": provider,
            "families": [provider],
            "parameter_size": "dynamic",
            "quantization_level": "dynamic",
        },
    }


def _require_router(request: Request) -> Any:
    router_instance = getattr(request.app.state, "router", None)
    if router_instance is None:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return router_instance


@router.post("/chat/completions")
async def create_chat_completion(
    request_body: ChatCompletionRequest,
    request: Request,
):
    """Create a chat completion (OpenAI-compatible endpoint)."""
    router_instance = _require_router(request)
    strategy, routing_policy, provider, model_name, display_model = _resolve_requested_routing(
        router_instance=router_instance,
        model=request_body.model,
        strategy=request_body.strategy,
        routing_policy=request_body.routing_policy,
    )
    messages, system_prompt, all_messages = _split_messages(request_body.messages)
    max_tokens = request_body.max_tokens if request_body.max_tokens is not None else 4096
    response_format_dict = _response_format_from_openai(request_body)

    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=request_body.project_id or _default_project_id(),
            federation_scope=request_body.federation_scope,
            knowledge_scope=request_body.knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request_body.stream:
        return await _handle_streaming(
            router_instance=router_instance,
            messages=all_messages if system_prompt else messages,
            provider=provider,
            model_name=model_name,
            display_model=display_model,
            system=None if system_prompt else system_prompt,
            temperature=request_body.temperature,
            max_tokens=max_tokens,
            strategy=strategy,
            routing_policy=routing_policy,
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )

    try:
        llm_response = await router_instance.send(
            messages=messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model_name,
            system=system_prompt,
            response_format=response_format_dict,
            temperature=request_body.temperature,
            max_tokens=max_tokens,
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )

        usage = None
        if llm_response.usage:
            input_tokens = llm_response.usage.get("input_tokens", 0)
            output_tokens = llm_response.usage.get("output_tokens", 0)
            total = llm_response.usage.get("total_tokens", 0) or (input_tokens + output_tokens)
            usage = ChatCompletionUsage(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=total,
            )

        response_model = display_model
        if display_model in AUTO_ROUTE_MODEL_POLICIES or request_body.model is None:
            response_model = _format_response_model(
                llm_response.provider,
                llm_response.model,
                fallback=display_model,
            )

        return ChatCompletionResponse(
            id=f"chatcmpl-{secrets.token_hex(12)}",
            object="chat.completion",
            created=int(time.time()),
            model=response_model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=llm_response.content,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=usage,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(exc)}",
        ) from exc


@ollama_router.post("/api/chat")
async def create_ollama_chat_completion(
    request_body: OllamaChatRequest,
    request: Request,
):
    """Ollama-compatible chat shim backed by the Mascarade router."""
    router_instance = _require_router(request)
    strategy, routing_policy, provider, model_name, display_model = _resolve_requested_routing(
        router_instance=router_instance,
        model=request_body.model,
        strategy=request_body.strategy,
        routing_policy=request_body.routing_policy,
    )
    messages, system_prompt, all_messages = _split_messages(request_body.messages)
    temperature, max_tokens = _ollama_generation_params(request_body.options)
    response_format = _response_format_from_ollama(request_body.format)

    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=request_body.project_id or _default_project_id(),
            federation_scope=request_body.federation_scope,
            knowledge_scope=request_body.knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request_body.stream:
        return await _handle_ollama_stream(
            router_instance=router_instance,
            messages=all_messages if system_prompt else messages,
            provider=provider,
            model_name=model_name,
            display_model=display_model,
            system=None if system_prompt else system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            strategy=strategy,
            routing_policy=routing_policy,
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
            payload_builder=_ollama_chat_payload,
        )

    try:
        llm_response = await router_instance.send(
            messages=messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model_name,
            system=system_prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    prompt_tokens = int((llm_response.usage or {}).get("input_tokens", 0))
    completion_tokens = int((llm_response.usage or {}).get("output_tokens", 0))
    response_model = display_model
    if display_model in AUTO_ROUTE_MODEL_POLICIES or request_body.model is None:
        response_model = _format_response_model(
            llm_response.provider,
            llm_response.model,
            fallback=display_model,
        )
    return _ollama_chat_payload(
        model=response_model,
        content=llm_response.content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        done=True,
    )


@ollama_router.post("/api/generate")
async def create_ollama_generate_completion(
    request_body: OllamaGenerateRequest,
    request: Request,
):
    """Ollama-compatible generate shim backed by the Mascarade router."""
    router_instance = _require_router(request)
    strategy, routing_policy, provider, model_name, display_model = _resolve_requested_routing(
        router_instance=router_instance,
        model=request_body.model,
        strategy=request_body.strategy,
        routing_policy=request_body.routing_policy,
    )
    temperature, max_tokens = _ollama_generation_params(request_body.options)
    response_format = _response_format_from_ollama(request_body.format)

    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=request_body.project_id or _default_project_id(),
            federation_scope=request_body.federation_scope,
            knowledge_scope=request_body.knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    base_messages = [{"role": "user", "content": request_body.prompt}]
    if request_body.stream:
        return await _handle_ollama_stream(
            router_instance=router_instance,
            messages=base_messages,
            provider=provider,
            model_name=model_name,
            display_model=display_model,
            system=request_body.system,
            temperature=temperature,
            max_tokens=max_tokens,
            strategy=strategy,
            routing_policy=routing_policy,
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
            payload_builder=_ollama_generate_payload,
        )

    try:
        llm_response = await router_instance.send(
            messages=base_messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model_name,
            system=request_body.system,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    prompt_tokens = int((llm_response.usage or {}).get("input_tokens", 0))
    completion_tokens = int((llm_response.usage or {}).get("output_tokens", 0))
    response_model = display_model
    if display_model in AUTO_ROUTE_MODEL_POLICIES or request_body.model is None:
        response_model = _format_response_model(
            llm_response.provider,
            llm_response.model,
            fallback=display_model,
        )
    return _ollama_generate_payload(
        model=response_model,
        content=llm_response.content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        done=True,
    )


@ollama_router.get("/api/tags")
async def list_ollama_models(request: Request):
    """Ollama-compatible tag catalog for Mascarade-routed models."""
    router_instance = _require_router(request)
    models = [
        _ollama_tag_entry(auto_model, provider="mascarade")
        for auto_model in AUTO_ROUTE_MODEL_POLICIES
    ]
    provider_model_map = _provider_model_map(router_instance)
    for provider in sorted(provider_model_map):
        for model in sorted(set(provider_model_map[provider])):
            models.append(
                _ollama_tag_entry(
                    f"{provider}:{model}",
                    provider=provider,
                    parent_model=model,
                )
            )
    return {"models": models}


async def _handle_streaming(
    *,
    router_instance: Any,
    messages: list[dict[str, Any]],
    provider: str | None,
    model_name: str | None,
    display_model: str,
    system: str | None,
    temperature: float,
    max_tokens: int,
    strategy: Strategy = Strategy.SPECIFIC,
    routing_policy: str | None = None,
    project_id: str | None = None,
    federation_scope: list[str] | tuple[str, ...] | None = None,
    knowledge_scope: str = "project",
) -> StreamingResponse:
    """Handle a streaming chat completion request using SSE."""
    completion_id = f"chatcmpl-{secrets.token_hex(12)}"
    created = int(time.time())

    async def event_generator():
        first_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": display_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(first_chunk)}\n\n"

        async for token in router_instance.stream(
            messages=messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model_name,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        ):
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": display_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": token},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": display_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


async def _handle_ollama_stream(
    *,
    router_instance: Any,
    messages: list[dict[str, Any]],
    provider: str | None,
    model_name: str | None,
    display_model: str,
    system: str | None,
    temperature: float,
    max_tokens: int,
    strategy: Strategy,
    routing_policy: str | None,
    project_id: str,
    federation_scope: list[str] | tuple[str, ...] | None,
    knowledge_scope: str,
    payload_builder: Any,
) -> StreamingResponse:
    """Handle an Ollama-compatible streaming response using NDJSON."""

    async def event_generator():
        async for token in router_instance.stream(
            messages=messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model_name,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        ):
            chunk = payload_builder(
                model=display_model,
                content=token,
                prompt_tokens=0,
                completion_tokens=0,
                done=False,
            )
            yield json.dumps(chunk) + "\n"

        final_chunk = payload_builder(
            model=display_model,
            content="",
            prompt_tokens=0,
            completion_tokens=0,
            done=True,
        )
        yield json.dumps(final_chunk) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
    )
