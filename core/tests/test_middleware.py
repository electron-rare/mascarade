"""Tests for mascarade middleware — rate limit, body limit, log filter."""

from __future__ import annotations

import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.middleware.body_limit import BodySizeLimitMiddleware, MAX_BODY_BYTES
from mascarade.middleware.log_filter import SecretMaskingFilter, mask_secrets
from mascarade.middleware.rate_limit import RateLimitMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(path: str = "/api/chat", client_ip: str = "127.0.0.1", content_length: str | None = None):
    """Build a minimal mock Starlette Request."""
    req = MagicMock()
    req.url.path = path
    req.client.host = client_ip
    headers = {}
    if content_length is not None:
        headers["content-length"] = content_length
    req.headers = headers
    return req


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_allow_under_limit(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app, requests_per_minute=60, burst=10)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req = _make_request()
        resp = await mw.dispatch(req, call_next)

        call_next.assert_awaited_once_with(req)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_block_over_limit(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app, requests_per_minute=60, burst=2)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req = _make_request()
        # Drain the bucket
        await mw.dispatch(req, call_next)
        await mw.dispatch(req, call_next)
        # Third request should be rejected
        resp = await mw.dispatch(req, call_next)
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_exempt_health_path(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app, requests_per_minute=60, burst=1)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req = _make_request(path="/health")
        # Even if bucket would be empty, exempt paths pass through
        resp = await mw.dispatch(req, call_next)
        assert resp.status_code == 200
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exempt_metrics_path(self):
        app = MagicMock()
        mw = RateLimitMiddleware(app, requests_per_minute=60, burst=1)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req = _make_request(path="/metrics")
        resp = await mw.dispatch(req, call_next)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# BodySizeLimitMiddleware
# ---------------------------------------------------------------------------

class TestBodySizeLimitMiddleware:
    @pytest.mark.asyncio
    async def test_allow_small_body(self):
        app = MagicMock()
        mw = BodySizeLimitMiddleware(app, max_bytes=1024)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req = _make_request(content_length="512")
        resp = await mw.dispatch(req, call_next)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_block_large_body(self):
        app = MagicMock()
        mw = BodySizeLimitMiddleware(app, max_bytes=1024)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req = _make_request(content_length="2048")
        resp = await mw.dispatch(req, call_next)
        assert resp.status_code == 413

    @pytest.mark.asyncio
    async def test_allow_no_content_length(self):
        app = MagicMock()
        mw = BodySizeLimitMiddleware(app, max_bytes=1024)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req = _make_request()  # no content-length header
        resp = await mw.dispatch(req, call_next)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# mask_secrets
# ---------------------------------------------------------------------------

class TestMaskSecrets:
    def test_mask_sk_key(self):
        text = "key is sk-abcdefghijklmnopqrstuvwxyz"
        result = mask_secrets(text)
        assert "sk-***" in result
        assert "abcdefghijklmnopqrstuvwxyz" not in result

    def test_mask_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = mask_secrets(text)
        assert "Bearer ***" in result

    def test_mask_hf_token(self):
        text = "token=hf_abcdefghijklmnopqrstuvwxyz"
        result = mask_secrets(text)
        assert "hf_***" in result
        assert "abcdefghijklmnopqrstuvwxyz" not in result

    def test_mask_aws_access_key(self):
        text = "aws_key=AKIAIOSFODNN7EXAMPLE"
        result = mask_secrets(text)
        assert "AKIA***" in result
        assert "IOSFODNN7EXAMPLE" not in result

    def test_mask_ghp_token(self):
        text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuv"
        result = mask_secrets(text)
        assert "ghp_***" in result

    def test_no_false_positive_on_short_strings(self):
        text = "sk-short"
        result = mask_secrets(text)
        # Short strings (< 20 chars after prefix) should NOT be masked
        assert result == text

    def test_plain_text_unchanged(self):
        text = "Hello, this is a normal log message"
        assert mask_secrets(text) == text


# ---------------------------------------------------------------------------
# SecretMaskingFilter
# ---------------------------------------------------------------------------

class TestSecretMaskingFilter:
    def test_filter_masks_msg(self):
        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="API key sk-abcdefghijklmnopqrstuvwxyz found",
            args=None, exc_info=None,
        )
        f.filter(record)
        assert "sk-***" in record.msg

    def test_filter_masks_tuple_args(self):
        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="key=%s",
            args=("sk-abcdefghijklmnopqrstuvwxyz",),
            exc_info=None,
        )
        f.filter(record)
        assert "sk-***" in record.args[0]

    def test_filter_masks_dict_args(self):
        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="safe message",
            args=None,
            exc_info=None,
        )
        # Manually set dict args after construction to avoid Python 3.14
        # LogRecord __init__ trying to index the dict.
        record.args = {"key": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
        f.filter(record)
        assert "Bearer ***" in record.args["key"]

    def test_filter_returns_true(self):
        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="safe", args=None, exc_info=None,
        )
        assert f.filter(record) is True
