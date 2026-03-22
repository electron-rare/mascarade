"""Pydantic schemas for Mascarade API requests and responses."""

from __future__ import annotations

from typing import Literal

from typing import Any

from pydantic import BaseModel, Field, model_validator


def _normalize_content(v: Any) -> str | None:
    """Normalize content field: accept str, list of parts, or None.

    Xcode Intelligence sends content as a list of parts:
    [{"text": "...", "type": "text"}] instead of a plain string.
    """
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts = []
        for item in v:
            if isinstance(item, dict):
                parts.append(item.get("text", str(item)))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts) if parts else None
    return str(v)


# --- Chat Completion Models (OpenAI-compatible) ---


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: Literal["system", "user", "assistant", "tool", "function"] = Field(
        description="The role of the message author"
    )
    content: Any = Field(
        default=None,
        description="The content of the message (string or array of content parts)",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_content_field(cls, values: Any) -> Any:
        if isinstance(values, dict) and "content" in values:
            values["content"] = _normalize_content(values["content"])
        return values
    name: str | None = Field(
        default=None, max_length=100, description="Optional name for the participant"
    )
    tool_call_id: str | None = Field(
        default=None, max_length=200, description="Tool call ID for tool role messages"
    )


class FunctionCall(BaseModel):
    """Function call details."""

    name: str = Field(max_length=100, description="The name of the function to call")
    arguments: str = Field(
        max_length=10_000, description="JSON-encoded function arguments"
    )


class ToolCall(BaseModel):
    """Tool call details."""

    id: str = Field(max_length=200, description="Unique ID for the tool call")
    type: Literal["function"] = Field(
        default="function", description="The type of tool call"
    )
    function: FunctionCall = Field(description="Function call details")


class ResponseFormat(BaseModel):
    """Response format configuration."""

    type: Literal["text", "json_object"] = Field(
        default="text", description="The format of the response"
    )


class ChatCompletionRequest(BaseModel):
    """Request model for chat completions endpoint (OpenAI-compatible)."""

    messages: list[ChatMessage] = Field(
        min_length=1, max_length=200, description="List of messages in the conversation"
    )
    model: str = Field(
        max_length=100,
        description="Model to use (e.g., 'gpt-4', 'claude-3-5-sonnet-20241022')",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature between 0 and 2",
    )
    max_tokens: int | None = Field(
        default=None,
        gt=0,
        le=128000,
        description="Maximum number of tokens to generate",
    )
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter (alternative to temperature)",
    )
    n: int = Field(
        default=1, ge=1, le=10, description="Number of completions to generate"
    )
    stream: bool = Field(
        default=False, description="Whether to stream partial responses"
    )
    stop: str | list[str] | None = Field(
        default=None, max_length=4, description="Stop sequences"
    )
    presence_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Presence penalty between -2.0 and 2.0",
    )
    frequency_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Frequency penalty between -2.0 and 2.0",
    )
    logit_bias: dict[str, float] | None = Field(
        default=None, description="Token ID to bias mapping"
    )
    user: str | None = Field(
        default=None, max_length=100, description="Unique user identifier"
    )
    response_format: ResponseFormat | None = Field(
        default=None, description="Response format configuration"
    )
    tools: list[dict] | None = Field(
        default=None, max_length=20, description="Available tools/functions"
    )
    tool_choice: str | dict | None = Field(
        default=None, description="Tool choice configuration"
    )


class ChatCompletionUsage(BaseModel):
    """Token usage statistics for a chat completion."""

    prompt_tokens: int = Field(ge=0, description="Number of tokens in the prompt")
    completion_tokens: int = Field(
        ge=0, description="Number of tokens in the completion"
    )
    total_tokens: int = Field(ge=0, description="Total number of tokens used")


class ChatCompletionMessage(BaseModel):
    """Message in a chat completion response."""

    role: Literal["assistant", "system", "user", "tool", "function"] = Field(
        description="The role of the message author"
    )
    content: Any = Field(
        default=None, description="The content of the message"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_content_field(cls, values: Any) -> Any:
        if isinstance(values, dict) and "content" in values:
            values["content"] = _normalize_content(values["content"])
        return values
    tool_calls: list[ToolCall] | None = Field(
        default=None, description="Tool calls made by the assistant"
    )
    function_call: FunctionCall | None = Field(
        default=None, description="Function call made by the assistant (deprecated)"
    )


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int = Field(ge=0, description="The index of this choice")
    message: ChatCompletionMessage = Field(description="The completion message")
    finish_reason: Literal[
        "stop", "length", "tool_calls", "content_filter", "function_call", "null"
    ] | None = Field(default=None, description="Why the completion finished")
    logprobs: dict | None = Field(
        default=None, description="Log probabilities (if requested)"
    )


class ChatCompletionResponse(BaseModel):
    """Response model for chat completions endpoint (OpenAI-compatible)."""

    id: str = Field(max_length=200, description="Unique completion ID")
    object: Literal["chat.completion"] = Field(
        default="chat.completion", description="Object type"
    )
    created: int = Field(ge=0, description="Unix timestamp of creation")
    model: str = Field(max_length=100, description="Model used for completion")
    choices: list[ChatCompletionChoice] = Field(
        min_length=1, description="List of completion choices"
    )
    usage: ChatCompletionUsage | None = Field(
        default=None, description="Token usage statistics"
    )
    system_fingerprint: str | None = Field(
        default=None, max_length=100, description="System fingerprint"
    )


class ChatCompletionChunk(BaseModel):
    """Streamed chunk for chat completions (SSE format)."""

    id: str = Field(max_length=200, description="Unique completion ID")
    object: Literal["chat.completion.chunk"] = Field(
        default="chat.completion.chunk", description="Object type"
    )
    created: int = Field(ge=0, description="Unix timestamp of creation")
    model: str = Field(max_length=100, description="Model used for completion")
    choices: list[dict] = Field(description="List of delta choices")
    system_fingerprint: str | None = Field(
        default=None, max_length=100, description="System fingerprint"
    )
