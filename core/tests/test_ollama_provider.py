"""Tests for the Ollama provider."""

from __future__ import annotations

import asyncio

import pytest

from mascarade.router.providers.ollama import OllamaProvider


def test_ollama_provider_uses_configured_timeout(monkeypatch):
    monkeypatch.setattr("mascarade.router.providers.ollama.settings.ollama_enabled", True)
    monkeypatch.setattr(
        "mascarade.router.providers.ollama.settings.ollama_base_url",
        "http://host.docker.internal:11435",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.ollama.settings.ollama_timeout_seconds",
        900.0,
    )

    provider = OllamaProvider()

    assert provider.is_configured is True
    assert provider._client.timeout.read == 900.0


def test_ollama_provider_send_timeout_is_explicit(monkeypatch):
    monkeypatch.setattr("mascarade.router.providers.ollama.settings.ollama_enabled", True)
    monkeypatch.setattr(
        "mascarade.router.providers.ollama.settings.ollama_base_url",
        "http://host.docker.internal:11435",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.ollama.settings.ollama_timeout_seconds",
        420.0,
    )

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def post(self, path, json):
            raise __import__("httpx").ReadTimeout("timed out")

    monkeypatch.setattr(
        "mascarade.router.providers.ollama.httpx.AsyncClient",
        _FakeAsyncClient,
    )

    provider = OllamaProvider()

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(
            provider.send(
                [{"role": "user", "content": "hello"}],
                model="qwen2.5:7b",
                max_tokens=768,
            )
        )

    message = str(exc.value)
    assert "Ollama local timeout after 420s" in message
    assert "qwen2.5:7b" in message
    assert "max_tokens=768" in message
    assert "Increase OLLAMA_TIMEOUT_SECONDS" in message
