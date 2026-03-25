"""Mistral AI Studio Provider - Integration with Mistral's cloud platform."""

from __future__ import annotations

import logging

try:
    from mistralai.client import MistralClient
    from mistralai.models.chat_completion import ChatMessage

    MISTRAL_STUDIO_AVAILABLE = True
except ImportError:
    MISTRAL_STUDIO_AVAILABLE = False
    MistralClient = object
    ChatMessage = object

from mascarade.router.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("mascarade.mistral_studio")


class MistralStudioProvider(LLMProvider):
    """Provider for Mistral AI Studio cloud services."""

    name: str = "mistral-studio"
    default_model: str = "mistral-large-latest"

    # Cost per 1M tokens (input, output) for Mistral Studio
    cost_per_million: tuple[float, float] = (0.25, 0.25)  # USD

    # Performance characteristics
    speed_rank: int = 2  # Fast cloud response
    quality_rank: int = 4  # High quality

    def __init__(self, api_key: str):
        if not MISTRAL_STUDIO_AVAILABLE:
            raise RuntimeError(
                "Mistral Studio client not available. "
                "Install with: pip install mistralai"
            )

        self.client = MistralClient(api_key=api_key)
        logger.info("Mistral Studio provider initialized")

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send request to Mistral Studio API."""
        # Convert messages to Mistral format
        chat_messages = []
        if system:
            chat_messages.append(ChatMessage(role="system", content=system))

        for msg in messages:
            chat_messages.append(ChatMessage(role=msg["role"], content=msg["content"]))

        # Call Mistral Studio API
        response = self.client.chat(
            model=model or self.default_model,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Convert to standard format
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = None,
    ) -> str:
        """Stream response from Mistral Studio."""
        # Convert messages
        chat_messages = []
        if system:
            chat_messages.append(ChatMessage(role="system", content=system))

        for msg in messages:
            chat_messages.append(ChatMessage(role=msg["role"], content=msg["content"]))

        # Stream from Mistral
        for chunk in self.client.chat_stream(
            model=model or self.default_model,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def available_models(self) -> list[str]:
        """Available Mistral Studio models."""
        return [
            "mistral-tiny",
            "mistral-small",
            "mistral-medium",
            "mistral-large-latest",
        ]

    async def close(self) -> None:
        """Clean up resources."""
        # Mistral client doesn't require explicit cleanup
        pass
