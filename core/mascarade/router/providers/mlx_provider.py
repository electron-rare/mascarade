"""MLX Provider for Apple Silicon - Optimized for Metal GPU."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

try:
    import mlx.core as mx
    import mlx.loss
    from mlx_lm import generate, load

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    logging.warning("MLX not available. Install with: pip install mlx mlx-lm")

from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
)
from mascarade.scheduler.scheduler import ScheduledRequest

logger = logging.getLogger("mascarade.mlx")


class MLXProvider(LLMProvider):
    """MLX provider optimized for Apple Silicon."""

    name: str = "mlx"
    default_model: str = "mlx-model"

    def __init__(
        self,
        model_path: str,
        device: str = "mps",
        max_tokens: int = 4096,
        quantization: str | None = None,
        **kwargs,
    ):
        if not MLX_AVAILABLE:
            raise RuntimeError("MLX is not installed. Please install mlx and mlx-lm.")

        self.model_path = model_path
        self.device = device
        self.max_tokens = max_tokens
        self.quantization = quantization
        self.model = None
        self.tokenizer = None
        self.kwargs = kwargs

    async def initialize(self) -> None:
        """Load model and tokenizer."""
        if self.model is None:
            logger.info(f"Loading MLX model: {self.model_path}")
            self.model, self.tokenizer = load(
                self.model_path, device=self.device, **self.kwargs
            )
            logger.info("MLX model loaded successfully")

    async def generate(
        self,
        request: ScheduledRequest,
        stream: bool = False,
    ) -> LLMResponse:
        """Generate response using MLX."""
        if self.model is None:
            await self.initialize()

        # Format prompt
        prompt = self._format_prompt(request.messages)

        # Generate response
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=request.max_tokens,
            temp=request.temperature,
            verbose=False,
        )

        # MLX doesn't support streaming yet, return full response
        return LLMResponse(
            content=response,
            model=self.model_path,
            usage={
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(response.split()),
                "total_tokens": len((prompt + response).split()),
            },
        )

    def _format_prompt(self, messages: list[dict]) -> str:
        """Format messages into a prompt string."""
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

    async def close(self) -> None:
        """Clean up resources."""
        # MLX doesn't require explicit cleanup
        self.model = None
        self.tokenizer = None

    def available_models(self) -> list[str]:
        """Liste des modèles disponibles."""
        return [self.model_path]

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Envoyer une requête au provider MLX."""
        request = ScheduledRequest(
            request_id="temp-id",
            model=model or self.model_path,
            messages=messages,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature,
        )
        return await self.generate(request)

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Streamer la réponse token par token."""
        # MLX doesn't support streaming yet
        response = await self.send(
            messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield response.content


class MLXWorker:
    """Worker specialized for MLX inference on Apple Silicon."""

    def __init__(
        self,
        node_id: str,
        model_path: str,
        device: str = "mps",
        **kwargs,
    ):
        self.node_id = node_id
        self.provider = MLXProvider(model_path, device=device, **kwargs)
        self.current_requests = {}

    async def initialize(self) -> None:
        """Initialize the MLX provider."""
        await self.provider.initialize()

    async def process_request(self, request: ScheduledRequest):
        """Process a single request."""
        response = await self.provider.generate(request)

        if hasattr(request, "complete_callback"):
            await request.complete_callback(response)

        return response

    async def get_status(self) -> dict:
        """Get worker status."""
        return {
            "node_id": self.node_id,
            "model": self.provider.model_path,
            "device": self.provider.device,
            "current_load": len(self.current_requests),
        }
