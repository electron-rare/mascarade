"""GPT-5.3 Codex Provider - Advanced agentic coding model."""

from __future__ import annotations

import json
import logging

try:
    import openai

    GPT53_CODEX_AVAILABLE = True
except ImportError:
    GPT53_CODEX_AVAILABLE = False
    openai = None

from mascarade.router.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("mascarade.gpt53_codex")


class GPT53CodexProvider(LLMProvider):
    """Provider for GPT-5.3 Codex - Advanced agentic coding model."""

    name: str = "gpt-5.3-codex"
    default_model: str = "gpt-5.3-codex"

    # Cost per 1M tokens for GPT-5.3 Codex
    cost_per_million: tuple[float, float] = (1.75, 14.0)  # USD

    # Performance characteristics
    speed_rank: int = 1  # Fastest available
    quality_rank: int = 5  # Highest quality

    def __init__(self, api_key: str, organization: str | None = None):
        if not GPT53_CODEX_AVAILABLE:
            raise RuntimeError(
                "OpenAI Python library not available. "
                "Install with: pip install openai"
            )

        self.client = openai.AsyncOpenAI(api_key=api_key, organization=organization)
        logger.info("GPT-5.3 Codex provider initialized")

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        tool_choice: str | None = "auto",
    ) -> LLMResponse:
        """Send request to GPT-5.3 Codex API."""
        # Prepare messages
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})

        chat_messages.extend(messages)

        # Call API
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )

        # Convert to standard format
        return LLMResponse(
            content=response.choices[0].message.content or "",
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
        tools: list[dict] | None = None,
        tool_choice: str | None = "auto",
    ) -> str:
        """Stream response from GPT-5.3 Codex."""
        # Prepare messages
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})

        chat_messages.extend(messages)

        # Stream from API
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def available_models(self) -> list[str]:
        """Available GPT-5.3 Codex models."""
        return ["gpt-5.3-codex"]

    async def close(self) -> None:
        """Clean up resources."""
        await self.client.close()


class GPT53CodexFunctionCalling:
    """Advanced function calling capabilities for GPT-5.3 Codex."""

    def __init__(self, provider: GPT53CodexProvider):
        self.provider = provider

    async def call_with_functions(
        self, messages: list[dict], functions: list[dict], **kwargs
    ) -> LLMResponse:
        """Call model with function calling capabilities."""
        # Convert functions to tools format
        tools = [{"type": "function", "function": func} for func in functions]

        return await self.provider.send(
            messages=messages, tools=tools, tool_choice="auto", **kwargs
        )

    async def call_with_interactive_workflow(
        self, messages: list[dict], functions: list[dict], max_turns: int = 5
    ) -> list[LLMResponse]:
        """Handle multi-turn function calling workflow."""
        responses = []
        current_messages = messages.copy()

        for _ in range(max_turns):
            # Get response with function calls
            response = await self.call_with_functions(current_messages, functions)
            responses.append(response)

            # Check if function needs to be called
            if hasattr(response, "tool_calls"):
                # Execute functions and add results to messages
                for tool_call in response.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)

                    # Find and execute the function
                    func = next(f for f in functions if f["name"] == func_name)
                    func_result = func["implementation"](**func_args)

                    # Add function result to messages
                    current_messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(func_result),
                            "tool_call_id": tool_call.id,
                        }
                    )
            else:
                break

        return responses
