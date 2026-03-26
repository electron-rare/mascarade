"""Tests for the local lightweight server (mascarade.local_server)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Guard against missing anthropic — the module imports it at top level.
anthropic = pytest.importorskip("anthropic")


class TestResolveModel:
    """Tests for resolve_model helper."""

    def test_explicit_provider_model(self):
        with patch.dict(
            "mascarade.local_server.PROVIDERS",
            {"mistral": {"models": ["mistral-large-latest"]}},
        ):
            from mascarade.local_server import resolve_model

            provider, model = resolve_model("mistral:mistral-large-latest")
        assert provider == "mistral"
        assert model == "mistral-large-latest"

    def test_plain_model_name_found_in_provider(self):
        with patch.dict(
            "mascarade.local_server.PROVIDERS",
            {"openai": {"models": ["gpt-4o", "gpt-4o-mini"]}},
        ):
            from mascarade.local_server import resolve_model

            provider, model = resolve_model("gpt-4o")
        assert provider == "openai"
        assert model == "gpt-4o"

    def test_unknown_model_defaults_to_mistral_if_key_exists(self):
        with (
            patch.dict(
                "mascarade.local_server.PROVIDERS",
                {"mistral": {"models": ["mistral-large-latest"]}},
            ),
            patch("mascarade.local_server.MISTRAL_API_KEY", "sk-test"),
        ):
            from mascarade.local_server import resolve_model

            provider, model = resolve_model("unknown-model")
        assert provider == "mistral"

    def test_unknown_model_raises_without_mistral_key(self):
        from fastapi import HTTPException

        with (
            patch.dict("mascarade.local_server.PROVIDERS", {}),
            patch("mascarade.local_server.MISTRAL_API_KEY", ""),
        ):
            from mascarade.local_server import resolve_model

            with pytest.raises(HTTPException) as exc_info:
                resolve_model("unknown-model")
            assert exc_info.value.status_code == 404


class TestOllamaResultToOpenAI:
    """Tests for ollama_result_to_openai_chat_completion."""

    def test_converts_basic_result(self):
        from mascarade.local_server import ollama_result_to_openai_chat_completion

        ollama = {
            "model": "mistral-large",
            "message": {"role": "assistant", "content": "Hello!"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        result = ollama_result_to_openai_chat_completion(ollama, "mistral-large")

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["message"]["content"] == "Hello!"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5
        assert result["usage"]["total_tokens"] == 15

    def test_handles_empty_message(self):
        from mascarade.local_server import ollama_result_to_openai_chat_completion

        result = ollama_result_to_openai_chat_completion({}, "test-model")
        assert result["choices"][0]["message"]["content"] == ""
        assert result["model"] == "test-model"

    def test_handles_non_dict_message(self):
        from mascarade.local_server import ollama_result_to_openai_chat_completion

        # message is not a dict — should still produce empty content
        result = ollama_result_to_openai_chat_completion({"message": "not-a-dict"}, "test")
        assert result["choices"][0]["message"]["content"] == ""


class TestMistralChat:
    """Tests for mistral_chat."""

    @pytest.mark.asyncio
    async def test_non_streaming_success(self):
        from unittest.mock import MagicMock

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }

        with (
            patch("mascarade.local_server.MISTRAL_API_KEY", "sk-test"),
            patch("mascarade.local_server.httpx.AsyncClient") as mock_client,
        ):
            mock_instance = AsyncMock()
            mock_instance.post.return_value = fake_response
            mock_instance.aclose = AsyncMock()
            mock_client.return_value = mock_instance

            from mascarade.local_server import mistral_chat

            result = await mistral_chat(
                [{"role": "user", "content": "hi"}],
                model="mistral-large-latest",
            )

        assert result["choices"][0]["message"]["content"] == "response"

    @pytest.mark.asyncio
    async def test_raises_when_no_api_key(self):
        from fastapi import HTTPException

        with patch("mascarade.local_server.MISTRAL_API_KEY", ""):
            from mascarade.local_server import mistral_chat

            with pytest.raises(HTTPException) as exc_info:
                await mistral_chat([{"role": "user", "content": "hi"}])
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_timeout_raises_504(self):
        from fastapi import HTTPException

        with (
            patch("mascarade.local_server.MISTRAL_API_KEY", "sk-test"),
            patch("mascarade.local_server.httpx.AsyncClient") as mock_client,
        ):
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("timeout")
            mock_instance.aclose = AsyncMock()
            mock_client.return_value = mock_instance

            from mascarade.local_server import mistral_chat

            with pytest.raises(HTTPException) as exc_info:
                await mistral_chat([{"role": "user", "content": "hi"}])
            assert exc_info.value.status_code == 504


class TestClaudeChat:
    """Tests for claude_chat."""

    @pytest.mark.asyncio
    async def test_raises_when_no_api_key(self):
        from fastapi import HTTPException

        with patch("mascarade.local_server.ANTHROPIC_API_KEY", ""):
            from mascarade.local_server import claude_chat

            with pytest.raises(HTTPException) as exc_info:
                await claude_chat([{"role": "user", "content": "hi"}])
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_system_messages_extracted(self):
        fake_usage = type("U", (), {"input_tokens": 10, "output_tokens": 5})()
        fake_block = type("B", (), {"text": "Claude response"})()
        fake_response = type("R", (), {"content": [fake_block], "usage": fake_usage})()

        with (
            patch("mascarade.local_server.ANTHROPIC_API_KEY", "sk-ant-test"),
            patch("mascarade.local_server.anthropic.AsyncAnthropic") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create.return_value = fake_response
            mock_cls.return_value = mock_client

            from mascarade.local_server import claude_chat

            result = await claude_chat(
                [
                    {"role": "system", "content": "Be brief"},
                    {"role": "user", "content": "hi"},
                ]
            )

        assert result["content"] == "Claude response"
        assert result["usage"]["prompt_tokens"] == 10
        # Verify system was extracted
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "Be brief" in call_kwargs["system"]


class TestHealthEndpoint:
    """Tests for the /health endpoint using the ASGI test client."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        with (
            patch.dict("mascarade.local_server.PROVIDERS", {}),
            patch(
                "mascarade.local_server.provider_status_payload",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            from mascarade.local_server import app

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"


class TestTryP2PForward:
    """Tests for try_p2p_forward."""

    @pytest.mark.asyncio
    async def test_returns_none_with_no_peers(self):
        with patch("mascarade.local_server.P2P_PEERS", []):
            from mascarade.local_server import try_p2p_forward

            result = await try_p2p_forward([{"role": "user", "content": "hi"}], "model")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_result_from_first_reachable_peer(self):
        from contextlib import asynccontextmanager
        from unittest.mock import MagicMock

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "message": {"role": "assistant", "content": "peer response"},
            "done": True,
        }

        mock_instance = AsyncMock()
        mock_instance.post.return_value = fake_response

        @asynccontextmanager
        async def _fake_client(*_a, **_kw):
            yield mock_instance

        with (
            patch("mascarade.local_server.P2P_PEERS", ["http://peer1:8100"]),
            patch("mascarade.local_server.httpx.AsyncClient", side_effect=_fake_client),
        ):
            from mascarade.local_server import try_p2p_forward

            result = await try_p2p_forward([{"role": "user", "content": "hi"}], "model")

        assert result is not None
        assert result["_routed_via"] == "http://peer1:8100"

    @pytest.mark.asyncio
    async def test_returns_none_when_all_peers_fail(self):
        from contextlib import asynccontextmanager

        mock_instance = AsyncMock()
        mock_instance.post.side_effect = Exception("unreachable")

        @asynccontextmanager
        async def _fake_client(*_a, **_kw):
            yield mock_instance

        with (
            patch("mascarade.local_server.P2P_PEERS", ["http://peer1:8100"]),
            patch("mascarade.local_server.httpx.AsyncClient", side_effect=_fake_client),
        ):
            from mascarade.local_server import try_p2p_forward

            result = await try_p2p_forward([{"role": "user", "content": "hi"}], "model")

        assert result is None


class TestProbeProviderStatus:
    """Tests for probe_provider_status."""

    @pytest.mark.asyncio
    async def test_unconfigured_provider(self):
        with (
            patch.dict("mascarade.local_server.PROVIDERS", {}),
            patch.dict("mascarade.local_server.PROVIDER_PROBE_CACHE", {}, clear=True),
        ):
            from mascarade.local_server import probe_provider_status

            result = await probe_provider_status("nonexistent", force=True)

        assert result["configured"] is False
        assert result["ready"] is False

    @pytest.mark.asyncio
    async def test_uses_cache_within_ttl(self):
        import time

        cached = {
            "name": "mistral",
            "configured": True,
            "active": True,
            "ready": True,
            "error": None,
            "checked_at": time.time(),
        }

        with patch.dict("mascarade.local_server.PROVIDER_PROBE_CACHE", {"mistral": cached}):
            from mascarade.local_server import probe_provider_status

            result = await probe_provider_status("mistral")

        assert result is cached
