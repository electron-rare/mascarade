"""Tests for mascarade.integrations.kb_handler — multi-tier KB search fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from mascarade.integrations.kb_handler import KBSearchHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KB_RESULTS = [{"id": "1", "text": "KB doc", "source": "kb"}]
_QDRANT_HIGH = [{"id": "2", "text": "Vector doc", "score": 0.85, "source": "qdrant"}]
_QDRANT_LOW = [{"id": "3", "text": "Vector doc", "score": 0.20, "source": "qdrant"}]
_WEB_RESULTS = [{"source": "web", "text": "Web result", "score": 0.0}]


# ---------------------------------------------------------------------------
# Scenario 1: KB provider succeeds
# ---------------------------------------------------------------------------


class TestKBSuccess:
    async def test_returns_kb_results(self):
        handler = KBSearchHandler()
        with patch.object(handler, "_search_kb", new=AsyncMock(return_value=_KB_RESULTS)):
            results = await handler.search("test query")
        assert results == _KB_RESULTS
        assert results[0]["source"] == "kb"

    async def test_qdrant_not_called_when_kb_succeeds(self):
        handler = KBSearchHandler()
        qdrant_mock = AsyncMock(return_value=_QDRANT_HIGH)
        with (
            patch.object(handler, "_search_kb", new=AsyncMock(return_value=_KB_RESULTS)),
            patch.object(handler, "_search_qdrant", new=qdrant_mock),
        ):
            await handler.search("test query")
        qdrant_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 2: KB timeout → Qdrant high-confidence fallback
# ---------------------------------------------------------------------------


class TestKBTimeoutFallbackToQdrant:
    async def test_qdrant_used_when_kb_times_out(self):
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=TimeoutError())
            ),
            patch.object(handler, "_search_qdrant", new=AsyncMock(return_value=_QDRANT_HIGH)),
            patch.object(handler, "_search_web", new=AsyncMock(return_value=[])),
        ):
            results = await handler.search("test query")
        assert any(r["source"] == "qdrant" for r in results)

    async def test_qdrant_used_when_kb_errors(self):
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=RuntimeError("connection refused"))
            ),
            patch.object(handler, "_search_qdrant", new=AsyncMock(return_value=_QDRANT_HIGH)),
            patch.object(handler, "_search_web", new=AsyncMock(return_value=[])),
        ):
            results = await handler.search("test query")
        assert results == _QDRANT_HIGH

    async def test_web_not_called_when_qdrant_score_above_threshold(self):
        handler = KBSearchHandler()
        web_mock = AsyncMock(return_value=_WEB_RESULTS)
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=TimeoutError())
            ),
            patch.object(handler, "_search_qdrant", new=AsyncMock(return_value=_QDRANT_HIGH)),
            patch.object(handler, "_search_web", new=web_mock),
            patch("mascarade.integrations.kb_handler.settings") as mock_settings,
        ):
            mock_settings.kb_search_timeout_seconds = 5.0
            mock_settings.kb_qdrant_score_threshold = 0.6
            mock_settings.kb_enable_web_fallback = True
            results = await handler.search("test query")
        # _QDRANT_HIGH has score=0.85 which is above threshold=0.6, so no web
        web_mock.assert_not_called()
        assert results == _QDRANT_HIGH


# ---------------------------------------------------------------------------
# Scenario 3: Qdrant low confidence → web fallback appended
# ---------------------------------------------------------------------------


class TestQdrantLowScoreAppendsWeb:
    async def test_web_appended_when_qdrant_score_below_threshold(self):
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=TimeoutError())
            ),
            patch.object(handler, "_search_qdrant", new=AsyncMock(return_value=_QDRANT_LOW)),
            patch.object(handler, "_search_web", new=AsyncMock(return_value=_WEB_RESULTS)),
            patch("mascarade.integrations.kb_handler.settings") as mock_settings,
        ):
            mock_settings.kb_search_timeout_seconds = 5.0
            mock_settings.kb_qdrant_score_threshold = 0.6
            mock_settings.kb_enable_web_fallback = True
            results = await handler.search("test query")
        sources = {r["source"] for r in results}
        assert "qdrant" in sources
        assert "web" in sources

    async def test_web_not_appended_when_disabled(self):
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=TimeoutError())
            ),
            patch.object(handler, "_search_qdrant", new=AsyncMock(return_value=_QDRANT_LOW)),
            patch.object(handler, "_search_web", new=AsyncMock(return_value=_WEB_RESULTS)),
            patch("mascarade.integrations.kb_handler.settings") as mock_settings,
        ):
            mock_settings.kb_search_timeout_seconds = 5.0
            mock_settings.kb_qdrant_score_threshold = 0.6
            mock_settings.kb_enable_web_fallback = False
            results = await handler.search("test query")
        assert results == _QDRANT_LOW

    async def test_web_only_when_qdrant_empty(self):
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=RuntimeError("down"))
            ),
            patch.object(handler, "_search_qdrant", new=AsyncMock(return_value=[])),
            patch.object(handler, "_search_web", new=AsyncMock(return_value=_WEB_RESULTS)),
            patch("mascarade.integrations.kb_handler.settings") as mock_settings,
        ):
            mock_settings.kb_search_timeout_seconds = 5.0
            mock_settings.kb_qdrant_score_threshold = 0.6
            mock_settings.kb_enable_web_fallback = True
            results = await handler.search("test query")
        assert results == _WEB_RESULTS


# ---------------------------------------------------------------------------
# Scenario 4: All sources fail → empty result
# ---------------------------------------------------------------------------


class TestAllSourcesFail:
    async def test_returns_empty_list_when_all_fail(self):
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=RuntimeError("kb down"))
            ),
            patch.object(
                handler, "_search_qdrant", new=AsyncMock(side_effect=RuntimeError("qdrant down"))
            ),
            patch.object(handler, "_search_web", new=AsyncMock(return_value=[])),
            patch("mascarade.integrations.kb_handler.settings") as mock_settings,
        ):
            mock_settings.kb_search_timeout_seconds = 5.0
            mock_settings.kb_qdrant_score_threshold = 0.6
            mock_settings.kb_enable_web_fallback = True
            results = await handler.search("test query")
        assert results == []

    async def test_never_raises_to_caller(self):
        """KBSearchHandler must not propagate exceptions to its callers."""
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=RuntimeError("kb down"))
            ),
            patch.object(
                handler, "_search_qdrant", new=AsyncMock(side_effect=RuntimeError("qdrant down"))
            ),
            patch.object(handler, "_search_web", new=AsyncMock(return_value=[])),
            patch("mascarade.integrations.kb_handler.settings") as mock_settings,
        ):
            mock_settings.kb_search_timeout_seconds = 5.0
            mock_settings.kb_qdrant_score_threshold = 0.6
            mock_settings.kb_enable_web_fallback = False
            # Should not raise
            results = await handler.search("query that breaks everything")
        assert isinstance(results, list)


class TestSearchHardening:
    async def test_returns_empty_list_for_blank_query(self):
        handler = KBSearchHandler()
        kb_mock = AsyncMock(return_value=_KB_RESULTS)
        with patch.object(handler, "_search_kb", new=kb_mock):
            results = await handler.search("   ")
        assert results == []
        kb_mock.assert_not_called()

    async def test_web_fallback_error_does_not_raise(self):
        handler = KBSearchHandler()
        with (
            patch.object(
                handler, "_search_kb", new=AsyncMock(side_effect=RuntimeError("kb down"))
            ),
            patch.object(handler, "_search_qdrant", new=AsyncMock(return_value=_QDRANT_LOW)),
            patch.object(
                handler,
                "_search_web",
                new=AsyncMock(side_effect=RuntimeError("web down")),
            ),
            patch("mascarade.integrations.kb_handler.settings") as mock_settings,
        ):
            mock_settings.kb_qdrant_score_threshold = 0.6
            mock_settings.kb_enable_web_fallback = True
            results = await handler.search("test query")
        assert results == _QDRANT_LOW


# ---------------------------------------------------------------------------
# Limit and parameter forwarding
# ---------------------------------------------------------------------------


class TestParameterForwarding:
    async def test_limit_forwarded_to_kb(self):
        handler = KBSearchHandler()
        kb_mock = AsyncMock(return_value=_KB_RESULTS)
        with patch.object(handler, "_search_kb", new=kb_mock):
            await handler.search("query", limit=7)
        kb_mock.assert_awaited_once()
        _, kwargs = kb_mock.call_args
        assert kwargs.get("limit") == 7 or kb_mock.call_args.args[1] == 7

    async def test_project_id_forwarded(self):
        handler = KBSearchHandler()
        kb_mock = AsyncMock(return_value=_KB_RESULTS)
        with patch.object(handler, "_search_kb", new=kb_mock):
            await handler.search("query", project_id="proj-123")
        kb_mock.assert_awaited_once()
        kwargs = kb_mock.call_args.kwargs
        assert kwargs.get("project_id") == "proj-123"

    async def test_limit_clamped_to_maximum(self):
        """Un limit > 50 doit être silencieusement ramené à 50."""
        handler = KBSearchHandler()
        kb_mock = AsyncMock(return_value=_KB_RESULTS)
        with patch.object(handler, "_search_kb", new=kb_mock):
            await handler.search("query", limit=999)
        _, kwargs = kb_mock.call_args
        effective = kwargs.get("limit") or kb_mock.call_args.args[1]
        assert effective <= 50

    async def test_limit_clamped_to_minimum(self):
        """Un limit ≤ 0 doit être silencieusement ramené à 1."""
        handler = KBSearchHandler()
        kb_mock = AsyncMock(return_value=_KB_RESULTS)
        with patch.object(handler, "_search_kb", new=kb_mock):
            await handler.search("query", limit=0)
        _, kwargs = kb_mock.call_args
        effective = kwargs.get("limit") or kb_mock.call_args.args[1]
        assert effective >= 1

    async def test_filters_non_dict_results(self):
        """Les résultats non-dict (None, str, etc.) doivent être ignorés."""
        handler = KBSearchHandler()
        mixed_results = [_KB_RESULTS[0], None, "corrupted", 42]  # type: ignore[list-item]
        with patch.object(handler, "_search_kb", new=AsyncMock(return_value=mixed_results)):
            results = await handler.search("test query")
        assert all(isinstance(r, dict) for r in results)
        assert len(results) == 1
