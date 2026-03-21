"""OpenAI-compatible chat completions shim."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mascarade.config import settings
from mascarade.router.router import Strategy

logger = logging.getLogger("mascarade.routes.compat")

router = APIRouter()


class _OAIChatMessage(BaseModel):
    role: str
    content: str


class _OAIChatRequest(BaseModel):
    model: str | None = None
    messages: list[_OAIChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096


@router.post("/v1/chat/completions")
async def openai_chat_completions(body: _OAIChatRequest, request: Request):
    llm_router = request.app.state.router

    raw_model = body.model or ""
    provider_name: str | None = None
    model_name: str | None = None

    if ":" in raw_model:
        prefix, rest = raw_model.split(":", 1)
        if prefix in llm_router.available_providers:
            provider_name = prefix
            model_name = rest
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model prefix '{prefix}'.",
            )
    else:
        provider_name = settings.default_provider
        model_name = raw_model or settings.default_model

    if provider_name and provider_name not in llm_router.available_providers:
        raise HTTPException(
            status_code=503,
            detail={
                "error": f"Provider '{provider_name}' is not configured or unavailable.",
                "providers": llm_router.available_providers,
            },
        )

    strategy = Strategy.SPECIFIC if provider_name else Strategy.BEST
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    result = await llm_router.send(
        messages,
        strategy=strategy,
        provider=provider_name,
        model=model_name,
        system=None,
        response_format=None,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    usage = result.usage or {}
    display_model = (
        f"{provider_name}:{result.model}"
        if provider_name and provider_name != settings.default_provider
        else result.model
    )

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": display_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get(
                "total_tokens",
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            ),
        },
    }
