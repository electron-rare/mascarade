"""Tests for the Apple Core ML provider."""

from __future__ import annotations

import asyncio

import pytest

from mascarade.router.providers.apple_coreml import AppleCoreMLProvider


def test_apple_provider_is_configured_when_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_enabled", True
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_base_url",
        "http://host.docker.internal:8201",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_model_id",
        "phi-3-mini-coreml",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_timeout_seconds",
        30.0,
    )

    provider = AppleCoreMLProvider()

    assert provider.is_configured is True
    assert provider.default_model == "phi-3-mini-coreml"


def test_apple_provider_send(monkeypatch):
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_enabled", True
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_base_url",
        "http://host.docker.internal:8201",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_model_id",
        "apple-local",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_timeout_seconds",
        30.0,
    )

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "content": "hello from ane",
                "model": "apple-local",
                "usage": {"input_tokens": 7, "output_tokens": 4},
            }

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.payload = None

        async def post(self, path, json):
            self.payload = (path, json)
            return _FakeResponse()

    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.httpx.AsyncClient",
        _FakeAsyncClient,
    )

    provider = AppleCoreMLProvider()
    response = asyncio.run(
        provider.send(
            [{"role": "user", "content": "hello"}],
            system="be concise",
            temperature=0.1,
            max_tokens=64,
        )
    )

    assert response.content == "hello from ane"
    assert response.provider == "apple-coreml"
    assert response.model == "apple-local"


def test_apple_provider_send_timeout_is_explicit(monkeypatch):
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_enabled", True
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_base_url",
        "http://host.docker.internal:8201",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_model_id",
        "apple-local",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_timeout_seconds",
        90.0,
    )

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def post(self, path, json):
            raise __import__("httpx").ReadTimeout("timed out")

    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.httpx.AsyncClient",
        _FakeAsyncClient,
    )

    provider = AppleCoreMLProvider()

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(
            provider.send(
                [{"role": "user", "content": "hello"}],
                max_tokens=128,
            )
        )

    message = str(exc.value)
    assert "Apple local timeout after 90s" in message
    assert "max_tokens=128" in message
    assert "Increase APPLE_LLM_TIMEOUT_SECONDS" in message


def test_apple_provider_available_models(monkeypatch):
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_enabled", True
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_base_url",
        "http://host.docker.internal:8201",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_model_id",
        "apple-local",
    )
    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.settings.apple_llm_timeout_seconds",
        30.0,
    )

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": ["apple-local"]}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path):
            assert path == "/models"
            return _FakeResponse()

    monkeypatch.setattr(
        "mascarade.router.providers.apple_coreml.httpx.Client", _FakeClient
    )

    provider = AppleCoreMLProvider()

    assert provider.available_models() == ["apple-local"]
