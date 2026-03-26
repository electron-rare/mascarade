"""Public routes mounted directly on the FastAPI app (no auth required)."""

from __future__ import annotations

import json
import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from mascarade.config import settings
from mascarade.observability import new_run_id
from mascarade.router.router import Strategy
from mascarade.server_models import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ModelListResponse,
    ModelObject,
)

logger = logging.getLogger("mascarade.server")


def register_public_routes(app: FastAPI) -> None:
    """Register all public (unauthenticated) routes on *app*."""

    @app.get("/health")
    async def health():
        """Health check endpoint - returns basic system status."""
        health_data = {"status": "ok"}

        # Add optional metrics if state is initialized
        if hasattr(app.state, "router"):
            health_data["providers"] = app.state.router.available_providers
        if hasattr(app.state, "registry"):
            health_data["agents"] = len(app.state.registry)

        return health_data

    @app.get("/v1/version")
    async def version():
        """Version endpoint - returns API version and service information."""
        return {"version": "v1", "service": "mascarade-core", "api_version": "0.1.0"}

    @app.get("/v1/models")
    async def list_models():
        """OpenAI-compatible models list endpoint."""
        if not hasattr(app.state, "router"):
            raise HTTPException(status_code=503, detail="Router not initialized")

        models: list[ModelObject] = []
        for provider_name, model_list in app.state.router.provider_model_map().items():
            for model_id in model_list:
                models.append(
                    ModelObject(
                        id=f"{provider_name}:{model_id}",
                        owned_by=provider_name,
                    )
                )
                # Also expose without prefix for the default provider
                if provider_name == settings.default_provider:
                    models.append(
                        ModelObject(
                            id=model_id,
                            owned_by=provider_name,
                        )
                    )

        return ModelListResponse(data=models)

    @app.get("/health/providers")
    async def get_provider_health():
        """Provider health metrics endpoint - returns detailed health statistics for all providers."""
        if not hasattr(app.state, "router"):
            raise HTTPException(status_code=503, detail="Router not initialized")

        health_monitor = app.state.router.health_monitor
        circuit_breaker = app.state.router.circuit_breaker
        all_health = health_monitor.get_all_health()

        # Convert ProviderHealth dataclass objects to dictionaries
        health_data = {}
        for provider_name, provider_health in all_health.items():
            circuit_state = circuit_breaker.get_state(provider_name)
            health_data[provider_name] = {
                "provider_name": provider_health.provider_name,
                "health_score": provider_health.health_score,
                "circuit_state": circuit_state.value,
                "latency_p50": provider_health.latency_p50,
                "latency_p95": provider_health.latency_p95,
                "latency_p99": provider_health.latency_p99,
                "error_rate": provider_health.error_rate,
                "availability": provider_health.availability,
                "total_requests": provider_health.total_requests,
            }

        return health_data

    @app.post("/v1/chat/completions")
    async def chat_completions(req: ChatCompletionRequest):
        """OpenAI-compatible chat completions endpoint."""
        # Determine model and provider
        model_str = req.model if req.model else settings.default_model
        provider = None
        model = model_str

        # Parse model string for provider prefix (e.g., "apple-coreml:model")
        if ":" in model_str:
            parts = model_str.split(":", 1)
            provider_prefix = parts[0]
            model = parts[1]

            # Get supported provider names dynamically from router + known aliases
            _provider_aliases = {"anthropic": "claude", "gemini": "google"}
            supported_providers = set(app.state.router.available_providers)
            supported_providers.update(_provider_aliases.keys())

            # Resolve alias before validation
            if provider_prefix in _provider_aliases:
                provider_prefix = _provider_aliases[provider_prefix]

            # Validate provider prefix
            if provider_prefix not in supported_providers:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported model prefix '{provider_prefix}'.",
                )

            provider = provider_prefix

            # Check if provider is available
            if provider not in app.state.router.available_providers:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": f"Provider '{provider}' is not configured or unavailable.",
                        "providers": app.state.router.available_providers,
                    },
                )
        else:
            # Use default provider if no prefix
            provider = settings.default_provider
            model = model_str or settings.default_model

        # Convert messages to router format
        messages = [{"role": m.role, "content": m.content} for m in req.messages]

        # Handle streaming if requested
        if req.stream:

            async def stream_response():
                """Generate SSE stream of chat completion chunks."""
                chat_id = f"chatcmpl-{new_run_id()}"
                created = int(time.time())

                # Send initial chunk with role
                initial_chunk = ChatCompletionChunk(
                    id=chat_id,
                    object="chat.completion.chunk",
                    created=created,
                    model=model_str,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(role="assistant"),
                            finish_reason=None,
                        )
                    ],
                )
                yield f"data: {initial_chunk.model_dump_json()}\n\n"

                # Stream tokens
                try:
                    async for token in app.state.router.stream(
                        messages,
                        strategy=Strategy.SPECIFIC,
                        provider=provider,
                        model=model,
                        system=None,
                        temperature=req.temperature,
                        max_tokens=req.max_tokens or 4096,
                    ):
                        chunk = ChatCompletionChunk(
                            id=chat_id,
                            object="chat.completion.chunk",
                            created=created,
                            model=model_str,
                            choices=[
                                ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionChunkDelta(content=token),
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

                    # Send final chunk with finish_reason
                    final_chunk = ChatCompletionChunk(
                        id=chat_id,
                        object="chat.completion.chunk",
                        created=created,
                        model=model_str,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(),
                                finish_reason="stop",
                            )
                        ],
                    )
                    yield f"data: {final_chunk.model_dump_json()}\n\n"

                except ValueError as exc:
                    logger.warning("Chat completions streaming failed: %s", exc)
                    # For streaming errors, we can't raise HTTPException
                    # Send an error in SSE format
                    error_data = {"error": {"message": str(exc), "type": "invalid_request_error"}}
                    yield f"data: {json.dumps(error_data)}\n\n"

                # Send [DONE] marker
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # Non-streaming response (original implementation)
        try:
            response = await app.state.router.send(
                messages,
                strategy=Strategy.SPECIFIC,
                provider=provider,
                model=model,
                system=None,
                response_format=None,
                temperature=req.temperature,
                max_tokens=req.max_tokens or 4096,
            )
        except ValueError as exc:
            logger.warning("Chat completions request rejected: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Build OpenAI-compatible response
        chat_id = f"chatcmpl-{new_run_id()}"
        created = int(time.time())

        # Extract usage info
        usage_dict = response.usage or {}
        prompt_tokens = usage_dict.get("input_tokens", 0)
        completion_tokens = usage_dict.get("output_tokens", 0)
        total_tokens = usage_dict.get("total_tokens", prompt_tokens + completion_tokens)

        usage = ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        choice = ChatCompletionChoice(
            index=0,
            message=ChatCompletionMessage(
                role="assistant",
                content=response.content,
            ),
            finish_reason="stop",
        )

        return ChatCompletionResponse(
            id=chat_id,
            object="chat.completion",
            created=created,
            model=model_str,
            choices=[choice],
            usage=usage,
        )

    @app.get("/metrics")
    async def prometheus_metrics():
        """Expose Prometheus metrics for scraping — no auth required."""
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
            from starlette.responses import Response

            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="prometheus_client is not installed",
            ) from None
