"""Chat completions endpoint - OpenAI-compatible API."""

from __future__ import annotations

import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from mascarade.models.schemas import ChatCompletionRequest, ChatCompletionResponse
from mascarade.models.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionUsage,
)
from mascarade.router.router import Strategy

router = APIRouter(tags=["chat"], prefix="/v1")


def _map_model_to_provider_and_model(model: str) -> tuple[str | None, str | None]:
    """
    Map a model string to provider and model name.

    Examples:
        "gpt-4" -> (None, "gpt-4")  # Let router decide provider
        "openai:gpt-4" -> ("openai", "gpt-4")
        "claude-3-5-sonnet-20241022" -> (None, "claude-3-5-sonnet-20241022")

    Args:
        model: Model string from the request

    Returns:
        Tuple of (provider_name, model_name)
    """
    if ":" in model:
        parts = model.split(":", 1)
        return (parts[0], parts[1])
    return (None, model)


@router.post("/chat/completions")
async def create_chat_completion(
    request_body: ChatCompletionRequest,
    request: Request,
) -> ChatCompletionResponse:
    """
    Create a chat completion (OpenAI-compatible endpoint).

    This is a frozen API contract that follows the OpenAI API specification.
    Any changes to this endpoint should maintain backward compatibility.

    Args:
        request_body: Chat completion request following OpenAI schema
        request: FastAPI request object for accessing app state

    Returns:
        ChatCompletionResponse following OpenAI schema

    Raises:
        HTTPException: If router is not initialized or request fails
    """
    if not hasattr(request.app.state, "router"):
        raise HTTPException(status_code=503, detail="Router not initialized")

    router_instance = request.app.state.router

    # Convert ChatMessage models to dict format expected by router
    messages = [
        {
            "role": msg.role,
            "content": msg.content or "",
            **({"name": msg.name} if msg.name else {}),
            **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
        }
        for msg in request_body.messages
    ]

    # Map model to provider and model name
    provider, model = _map_model_to_provider_and_model(request_body.model)

    # Determine max_tokens (use default if not specified)
    max_tokens = request_body.max_tokens if request_body.max_tokens is not None else 4096

    # Convert response_format to dict if present
    response_format_dict = None
    if request_body.response_format:
        response_format_dict = {"type": request_body.response_format.type}

    try:
        # Call router's send method
        llm_response = await router_instance.send(
            messages=messages,
            strategy=Strategy.BEST,  # Default to best strategy for API
            provider=provider,
            model=model,
            system=None,  # System message should be in messages array
            response_format=response_format_dict,
            temperature=request_body.temperature,
            max_tokens=max_tokens,
        )

        # Generate unique completion ID
        completion_id = f"chatcmpl-{secrets.token_hex(12)}"

        # Extract usage from LLM response
        usage = None
        if llm_response.usage:
            usage = ChatCompletionUsage(
                prompt_tokens=llm_response.usage.get("input_tokens", 0),
                completion_tokens=llm_response.usage.get("output_tokens", 0),
                total_tokens=(
                    llm_response.usage.get("input_tokens", 0)
                    + llm_response.usage.get("output_tokens", 0)
                ),
            )

        # Build response following OpenAI schema
        response = ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=int(time.time()),
            model=llm_response.model,
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
        # Handle validation or provider errors
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        # Handle router configuration errors
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        ) from e
