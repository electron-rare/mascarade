"""Chat completions endpoint - OpenAI-compatible API."""

from __future__ import annotations

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
)
from mascarade.router.router import Strategy

router = APIRouter(tags=["chat"], prefix="/v1")


# Known provider prefixes that may appear in model strings
SUPPORTED_PROVIDER_PREFIXES = frozenset(
    ["apple-coreml", "ollama", "openai", "claude", "mistral", "google", "mlx-lm", "huggingface"]
)


def _parse_model_string(
    model: str,
    router_instance: Any,
) -> tuple[str | None, str, str]:
    """Parse a model string into (provider, model_name, display_model).

    Handles:
    - "apple-coreml:qwen3.5-4b-onnx-q4f16" -> ("apple-coreml", "qwen3.5-4b-onnx-q4f16", "apple-coreml:qwen3.5-4b-onnx-q4f16")
    - "ollama:qwen3.5:9b" -> ("ollama", "qwen3.5:9b", "ollama:qwen3.5:9b")
    - "gpt-4" -> (default_provider, "gpt-4", "gpt-4")
    """
    # Get supported prefixes from router if available, else use defaults
    supported = getattr(router_instance, "supported_provider_names", None)
    if supported is None:
        supported = list(SUPPORTED_PROVIDER_PREFIXES)
    # Also include dynamically registered providers
    available = getattr(router_instance, "available_providers", [])
    if available:
        supported = list(set(supported) | set(available))

    # Try to match a known provider prefix
    if ":" in model:
        for prefix in supported:
            if model.startswith(prefix + ":"):
                model_name = model[len(prefix) + 1 :]
                return prefix, model_name, model
        # Unknown prefix
        prefix = model.split(":", 1)[0]
        if prefix not in supported:
            raise ValueError(f"Unsupported model prefix '{prefix}'.")
        model_name = model[len(prefix) + 1 :]
        return prefix, model_name, model

    # No prefix -- use default provider
    return None, model, model


@router.post("/chat/completions")
async def create_chat_completion(
    request_body: ChatCompletionRequest,
    request: Request,
):
    """
    Create a chat completion (OpenAI-compatible endpoint).

    Supports both regular and streaming responses. This is a frozen API
    contract that follows the OpenAI API specification.
    """
    if not hasattr(request.app.state, "router"):
        raise HTTPException(status_code=503, detail="Router not initialized")

    router_instance = request.app.state.router

    # Parse model string to extract provider prefix
    try:
        provider, model_name, display_model = _parse_model_string(
            request_body.model, router_instance
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Determine strategy and handle provider availability
    use_specific = provider is not None
    available = getattr(router_instance, "available_providers", [])

    if provider is not None:
        # Provider prefix was given -- check availability
        if available and provider not in available:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": f"Provider '{provider}' is not configured or unavailable.",
                    "providers": list(available),
                },
            )
    else:
        # No provider prefix -- use default provider if set, else let router decide
        default_prov = settings.default_provider
        if available and default_prov and default_prov in available:
            provider = default_prov
            model_name = request_body.model or settings.default_model
            use_specific = True
        elif available:
            # Use first available provider
            provider = available[0]
            model_name = request_body.model or None
            use_specific = True
        else:
            # No available_providers info -- pass through to router as-is
            provider = None
            model_name = request_body.model or None
            use_specific = False

    # Extract system messages and non-system messages
    system_parts: list[str] = []
    user_messages: list[dict] = []
    for msg in request_body.messages:
        msg_dict = {
            "role": msg.role,
            "content": msg.content or "",
            **({"name": msg.name} if msg.name else {}),
            **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
        }
        if msg.role == "system":
            system_parts.append(msg.content or "")
        else:
            user_messages.append(msg_dict)

    system_prompt = "\n".join(system_parts) if system_parts else None
    messages = user_messages if system_parts else [
        {
            "role": msg.role,
            "content": msg.content or "",
            **({"name": msg.name} if msg.name else {}),
            **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
        }
        for msg in request_body.messages
    ]

    # Determine max_tokens
    max_tokens = request_body.max_tokens if request_body.max_tokens is not None else 4096

    # Convert response_format to dict if present
    response_format_dict = None
    if request_body.response_format:
        response_format_dict = {"type": request_body.response_format.type}

    # Determine strategy
    strategy = Strategy.SPECIFIC if use_specific else Strategy.BEST

    # Handle streaming - keep all messages (including system) in the array
    if request_body.stream:
        all_messages = [
            {
                "role": msg.role,
                "content": msg.content or "",
                **({"name": msg.name} if msg.name else {}),
                **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
            }
            for msg in request_body.messages
        ]
        return await _handle_streaming(
            router_instance=router_instance,
            messages=all_messages,
            provider=provider,
            model_name=model_name,
            display_model=display_model,
            system=None,
            temperature=request_body.temperature,
            max_tokens=max_tokens,
            strategy=strategy,
        )

    # Non-streaming request
    strategy = Strategy.SPECIFIC if use_specific else Strategy.BEST
    try:
        llm_response = await router_instance.send(
            messages=messages,
            strategy=strategy,
            provider=provider,
            model=model_name,
            system=system_prompt,
            response_format=response_format_dict,
            temperature=request_body.temperature,
            max_tokens=max_tokens,
        )

        completion_id = f"chatcmpl-{secrets.token_hex(12)}"

        # Build usage from LLM response
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

        # Build model name for response - use display_model to include provider prefix
        resp_model = display_model

        response = ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=int(time.time()),
            model=resp_model,
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

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        ) from e


async def _handle_streaming(
    *,
    router_instance: Any,
    messages: list[dict],
    provider: str | None,
    model_name: str | None,
    display_model: str,
    system: str | None,
    temperature: float,
    max_tokens: int,
    strategy: Strategy = Strategy.SPECIFIC,
) -> StreamingResponse:
    """Handle a streaming chat completion request using SSE."""
    completion_id = f"chatcmpl-{secrets.token_hex(12)}"
    created = int(time.time())

    async def event_generator():
        # First chunk: role indicator
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

        # Content chunks from the router's stream
        async for token in router_instance.stream(
            messages=messages,
            strategy=strategy,
            provider=provider,
            model=model_name,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
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

        # Final chunk: finish_reason
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
