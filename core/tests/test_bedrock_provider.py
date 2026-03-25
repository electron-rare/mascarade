"""Tests for BedrockProvider — works even without boto3 installed."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure 'boto3' and 'botocore' are importable even when not installed.
# ---------------------------------------------------------------------------
_boto3_stub = ModuleType("boto3")
_boto3_stub.session = ModuleType("boto3.session")
_boto3_stub.session.Session = MagicMock

_botocore_stub = ModuleType("botocore")
_botocore_config = ModuleType("botocore.config")
_botocore_config.Config = MagicMock
_botocore_exceptions = ModuleType("botocore.exceptions")
_botocore_exceptions.BotoCoreError = type("BotoCoreError", (Exception,), {})
_botocore_exceptions.ClientError = type("ClientError", (Exception,), {
    "__init__": lambda self, error_response=None, operation_name=None: (
        Exception.__init__(self, str(error_response)),
        setattr(self, "response", error_response or {}),
    ) and None
})

for mod_name, mod in [
    ("boto3", _boto3_stub),
    ("boto3.session", _boto3_stub.session),
    ("botocore", _botocore_stub),
    ("botocore.config", _botocore_config),
    ("botocore.exceptions", _botocore_exceptions),
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mod

from mascarade.config import settings  # noqa: E402
from mascarade.router.providers.bedrock import BedrockProvider, _to_bedrock_messages  # noqa: E402

BEDROCK_SETTING_NAMES = [
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "aws_region",
    "aws_bedrock_model_id",
]


@pytest.fixture(autouse=True)
def restore_bedrock_settings():
    snapshot = {name: getattr(settings, name) for name in BEDROCK_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


def _make_converse_response(text: str = "bedrock-ok") -> dict:
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": 10, "outputTokens": 20},
    }


@pytest.mark.asyncio
async def test_bedrock_send():
    settings.aws_access_key_id = "AKIATEST123456789012"  # noqa: S105
    settings.aws_secret_access_key = "wJalrXUtnFEMI/EXAMPLE"  # noqa: S105
    settings.aws_region = "eu-west-1"

    mock_client = MagicMock()
    mock_client.converse.return_value = _make_converse_response()

    provider = BedrockProvider()
    provider._client = mock_client
    provider._ft_runtime = mock_client
    provider._ft_management = MagicMock()
    provider._ft_management.list_custom_models.return_value = {"modelSummaries": []}

    with patch(
        "mascarade.router.providers.bedrock.asyncio.to_thread",
        new=_fake_to_thread,
    ), patch(
        "mascarade.router.providers.bedrock.asyncio.wait_for",
        side_effect=_fake_wait_for,
    ):
        response = await provider.send([{"role": "user", "content": "hello"}])

    assert response.content == "bedrock-ok"
    assert response.provider == "bedrock"
    assert response.usage["input_tokens"] == 10
    assert response.usage["output_tokens"] == 20


@pytest.mark.asyncio
async def test_bedrock_send_with_system():
    settings.aws_access_key_id = "AKIATEST123456789012"  # noqa: S105
    settings.aws_secret_access_key = "wJalrXUtnFEMI/EXAMPLE"  # noqa: S105

    mock_client = MagicMock()
    mock_client.converse.return_value = _make_converse_response()

    provider = BedrockProvider()
    provider._client = mock_client
    provider._ft_runtime = mock_client
    provider._ft_management = MagicMock()
    provider._ft_management.list_custom_models.return_value = {"modelSummaries": []}

    with patch(
        "mascarade.router.providers.bedrock.asyncio.to_thread",
        new=_fake_to_thread,
    ), patch(
        "mascarade.router.providers.bedrock.asyncio.wait_for",
        side_effect=_fake_wait_for,
    ):
        response = await provider.send(
            [{"role": "user", "content": "hi"}],
            system="You are helpful.",
        )

    assert response.content == "bedrock-ok"
    call_kwargs = mock_client.converse.call_args
    assert call_kwargs.kwargs.get("system") == [{"text": "You are helpful."}]


def test_bedrock_is_configured():
    settings.aws_access_key_id = "AKIATEST123456789012"  # noqa: S105
    settings.aws_secret_access_key = "wJalrXUtnFEMI/EXAMPLE"  # noqa: S105
    provider = BedrockProvider()
    assert provider.is_configured is True


def test_bedrock_not_configured_no_keys():
    settings.aws_access_key_id = ""
    settings.aws_secret_access_key = ""
    provider = BedrockProvider()
    assert provider.is_configured is False


def test_bedrock_not_configured_missing_secret_key():
    settings.aws_access_key_id = "AKIATEST123456789012"  # noqa: S105
    settings.aws_secret_access_key = ""
    provider = BedrockProvider()
    assert provider.is_configured is False


def test_bedrock_available_models():
    provider = BedrockProvider()
    provider._ft_management = MagicMock()
    provider._ft_management.list_custom_models.return_value = {
        "modelSummaries": [
            {
                "modelName": "mascarade-stm32",
                "modelArn": "arn:aws:bedrock:us-west-2:123:custom-model/mascarade-stm32",
            },
        ]
    }
    provider._client = MagicMock()
    provider._ft_runtime = MagicMock()

    models = provider.available_models()
    assert settings.aws_bedrock_model_id in models
    assert "mascarade-stm32" in models


def test_to_bedrock_messages_normalizes_roles():
    messages = [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    result = _to_bedrock_messages(messages)

    assert result[0]["role"] == "user"  # system -> user
    assert result[0]["content"] == [{"text": "sys prompt"}]
    assert result[1]["role"] == "user"
    assert result[2]["role"] == "assistant"


def test_to_bedrock_messages_empty_content():
    messages = [{"role": "user"}]
    result = _to_bedrock_messages(messages)
    assert result[0]["content"] == [{"text": ""}]


# ---------- helpers ----------

async def _fake_to_thread(fn, *args, **kwargs):
    """Replacement for asyncio.to_thread that calls fn directly."""
    return fn(*args, **kwargs)


async def _fake_wait_for(coro, **kwargs):
    """Replacement for asyncio.wait_for that awaits the coroutine."""
    return await coro
