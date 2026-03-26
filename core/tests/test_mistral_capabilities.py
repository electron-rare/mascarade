"""Tests for Mistral Document AI and Audio Transcription capabilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

_FAKE_API_KEY = SecretStr("test-mistral-key-12345678")


# ---------------------------------------------------------------------------
# MistralDocumentAI
# ---------------------------------------------------------------------------


class TestMistralDocumentAI:
    """Tests for the Document AI integration."""

    @pytest.mark.asyncio
    async def test_ocr_image(self, tmp_path: Path):
        """OCR on an image returns concatenated markdown text."""
        from mascarade.integrations.mistral_capabilities import MistralDocumentAI

        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "pages": [
                {"index": 0, "markdown": "Hello world"},
                {"index": 1, "markdown": "Page 2 text"},
            ],
            "model": "mistral-ocr-latest",
        }

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            doc_ai = MistralDocumentAI()
            text = await doc_ai.ocr(str(img_file))

        assert "Hello world" in text
        assert "Page 2 text" in text

    @pytest.mark.asyncio
    async def test_process_document_with_prompt(self, tmp_path: Path):
        """process_document with prompt performs OCR then Q&A."""
        from mascarade.integrations.mistral_capabilities import MistralDocumentAI

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        ocr_resp = MagicMock()
        ocr_resp.status_code = 200
        ocr_resp.raise_for_status = MagicMock()
        ocr_resp.json.return_value = {
            "pages": [{"index": 0, "markdown": "Invoice total: 1234 EUR"}],
            "model": "mistral-ocr-latest",
        }

        chat_resp = MagicMock()
        chat_resp.status_code = 200
        chat_resp.raise_for_status = MagicMock()
        chat_resp.json.return_value = {
            "choices": [{"message": {"content": "The total is 1234 EUR."}}],
        }

        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/ocr" in url:
                return ocr_resp
            return chat_resp

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            ms.mistral_default_model = "mistral-large-latest"
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=mock_post)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            doc_ai = MistralDocumentAI()
            result = await doc_ai.process_document(str(pdf_file), prompt="What is the total?")

        assert result["answer"] == "The total is 1234 EUR."
        assert call_count == 2  # OCR + chat

    @pytest.mark.asyncio
    async def test_ocr_file_not_found(self):
        """Raise FileNotFoundError for missing file."""
        from mascarade.integrations.mistral_capabilities import MistralDocumentAI

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms:
            ms.mistral_api_key = _FAKE_API_KEY

            doc_ai = MistralDocumentAI()
            with pytest.raises(FileNotFoundError):
                await doc_ai.ocr("/nonexistent/file.png")

    @pytest.mark.asyncio
    async def test_ocr_no_api_key(self, tmp_path: Path):
        """Raise RuntimeError when API key not configured."""
        from mascarade.integrations.mistral_capabilities import MistralDocumentAI

        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms:
            ms.mistral_api_key = SecretStr("")

            doc_ai = MistralDocumentAI()
            with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
                await doc_ai.ocr(str(img_file))


# ---------------------------------------------------------------------------
# MistralAudioTranscription
# ---------------------------------------------------------------------------


class TestMistralAudioTranscription:
    """Tests for the Audio Transcription integration."""

    @pytest.mark.asyncio
    async def test_transcribe_bytes(self):
        """Transcribe raw bytes returns text."""
        from mascarade.integrations.mistral_capabilities import (
            MistralAudioTranscription,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "text": "Bonjour le monde",
        }

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            transcriber = MistralAudioTranscription()
            result = await transcriber.transcribe_bytes(
                b"fake audio data",
                filename="test.mp3",
                language="fr",
            )

        assert result["text"] == "Bonjour le monde"

    @pytest.mark.asyncio
    async def test_transcribe_file(self, tmp_path: Path):
        """Transcribe a local file delegates to transcribe_bytes."""
        from mascarade.integrations.mistral_capabilities import (
            MistralAudioTranscription,
        )

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"text": "Transcription OK"}

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            transcriber = MistralAudioTranscription()
            result = await transcriber.transcribe(str(audio_file))

        assert result["text"] == "Transcription OK"

    @pytest.mark.asyncio
    async def test_transcribe_file_not_found(self):
        """Raise FileNotFoundError for missing audio."""
        from mascarade.integrations.mistral_capabilities import (
            MistralAudioTranscription,
        )

        transcriber = MistralAudioTranscription()
        with pytest.raises(FileNotFoundError):
            await transcriber.transcribe("/nonexistent/audio.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_no_api_key(self):
        """Raise RuntimeError when API key not configured."""
        from mascarade.integrations.mistral_capabilities import (
            MistralAudioTranscription,
        )

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms:
            ms.mistral_api_key = SecretStr("")

            transcriber = MistralAudioTranscription()
            with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
                await transcriber.transcribe_bytes(b"data", filename="test.wav")

    @pytest.mark.asyncio
    async def test_transcribe_with_diarize(self):
        """Diarize flag is sent in the request."""
        from mascarade.integrations.mistral_capabilities import (
            MistralAudioTranscription,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "text": "Speaker 1: hello. Speaker 2: hi.",
        }

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            transcriber = MistralAudioTranscription()
            result = await transcriber.transcribe_bytes(
                b"fake audio",
                filename="meeting.mp3",
                language="en",
                diarize=True,
            )

        assert "Speaker" in result["text"]
        # Verify diarize was passed in form data
        call_kwargs = mock_client.post.call_args
        data = call_kwargs.kwargs.get("data", {})
        assert data.get("diarize") == "true"


# ---------------------------------------------------------------------------
# Router endpoints (unit tests via TestClient)
# ---------------------------------------------------------------------------


class TestMistralCapabilitiesRouter:
    """Tests for the FastAPI router endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client with auth disabled."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mascarade.routers.mistral_capabilities import router

        app = FastAPI()
        app.include_router(router)

        # Override auth dependency
        from mascarade.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: None

        return TestClient(app)

    def test_ocr_endpoint(self, client, tmp_path: Path):
        """POST /v1/api/mistral/ocr returns extracted text."""
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        with patch(
            "mascarade.integrations.mistral_capabilities.MistralDocumentAI.ocr",
            new_callable=AsyncMock,
            return_value="Extracted text from image",
        ):
            with open(img, "rb") as f:
                resp = client.post(
                    "/v1/api/mistral/ocr",
                    files={"file": ("test.png", f, "image/png")},
                )

        assert resp.status_code == 200
        assert resp.json()["text"] == "Extracted text from image"

    def test_transcribe_endpoint(self, client):
        """POST /v1/api/mistral/transcribe returns transcription."""
        with patch(
            "mascarade.integrations.mistral_capabilities.MistralAudioTranscription.transcribe_bytes",
            new_callable=AsyncMock,
            return_value={"text": "Bonjour"},
        ):
            resp = client.post(
                "/v1/api/mistral/transcribe",
                files={"file": ("test.mp3", b"fake audio", "audio/mpeg")},
                data={"language": "fr"},
            )

        assert resp.status_code == 200
        assert resp.json()["text"] == "Bonjour"

    def test_document_endpoint(self, client, tmp_path: Path):
        """POST /v1/api/mistral/document returns OCR result."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        with patch(
            "mascarade.integrations.mistral_capabilities.MistralDocumentAI.process_document",
            new_callable=AsyncMock,
            return_value={
                "pages": [{"markdown": "content"}],
                "model": "mistral-ocr-latest",
            },
        ):
            with open(pdf, "rb") as f:
                resp = client.post(
                    "/v1/api/mistral/document",
                    files={"file": ("test.pdf", f, "application/pdf")},
                )

        assert resp.status_code == 200
        assert resp.json()["pages"][0]["markdown"] == "content"

    def test_transcribe_no_api_key(self, client):
        """503 when API key not configured."""
        with patch(
            "mascarade.integrations.mistral_capabilities.MistralAudioTranscription.transcribe_bytes",
            new_callable=AsyncMock,
            side_effect=RuntimeError("MISTRAL_API_KEY not configured"),
        ):
            resp = client.post(
                "/v1/api/mistral/transcribe",
                files={"file": ("test.mp3", b"audio", "audio/mpeg")},
            )

        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# MistralEmbeddings
# ---------------------------------------------------------------------------


class TestMistralEmbeddings:
    """Tests for the Embeddings integration."""

    @pytest.mark.asyncio
    async def test_embed_single_text(self):
        """Embed a single text returns embedding vector."""
        from mascarade.integrations.mistral_capabilities import MistralEmbeddings

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "object": "list",
            "data": [{"object": "embedding", "embedding": [0.1, 0.2, 0.3], "index": 0}],
            "model": "mistral-embed",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            embedder = MistralEmbeddings()
            result = await embedder.embed(["hello world"])

        assert len(result["data"]) == 1
        assert result["data"][0]["embedding"] == [0.1, 0.2, 0.3]
        assert result["data"][0]["index"] == 0

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self):
        """Embed multiple texts returns multiple embedding vectors."""
        from mascarade.integrations.mistral_capabilities import MistralEmbeddings

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": [0.1, 0.2], "index": 0},
                {"object": "embedding", "embedding": [0.3, 0.4], "index": 1},
            ],
            "model": "mistral-embed",
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        }

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            embedder = MistralEmbeddings()
            result = await embedder.embed(["text one", "text two"])

        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_embed_no_api_key(self):
        """Raise RuntimeError when API key not configured."""
        from mascarade.integrations.mistral_capabilities import MistralEmbeddings

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms:
            ms.mistral_api_key = SecretStr("")

            embedder = MistralEmbeddings()
            with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
                await embedder.embed(["hello"])


# ---------------------------------------------------------------------------
# MistralClassifier
# ---------------------------------------------------------------------------


class TestMistralClassifier:
    """Tests for the Classifier / Moderation integration."""

    @pytest.mark.asyncio
    async def test_moderate(self):
        """Moderate text returns category flags."""
        from mascarade.integrations.mistral_capabilities import MistralClassifier

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "id": "mod-123",
            "model": "mistral-moderation-latest",
            "results": [
                {
                    "categories": {
                        "sexual": False,
                        "hate_and_discrimination": False,
                        "violence_and_threats": False,
                        "dangerous_and_criminal_content": False,
                        "selfharm": False,
                        "health": False,
                        "financial": False,
                        "law": False,
                        "pii": False,
                    },
                    "category_scores": {
                        "sexual": 0.01,
                        "hate_and_discrimination": 0.02,
                    },
                }
            ],
        }

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            classifier = MistralClassifier()
            result = await classifier.moderate(["This is a safe text."])

        assert len(result["results"]) == 1
        assert result["results"][0]["categories"]["sexual"] is False

    @pytest.mark.asyncio
    async def test_classify(self):
        """Classify text returns classification results."""
        from mascarade.integrations.mistral_capabilities import MistralClassifier

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "id": "cls-456",
            "model": "mistral-moderation-latest",
            "results": [{"categories": {"pii": True}}],
        }

        with (
            patch("mascarade.integrations.mistral_capabilities.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            classifier = MistralClassifier()
            result = await classifier.classify(["My email is test@example.com"])

        assert result["results"][0]["categories"]["pii"] is True

    @pytest.mark.asyncio
    async def test_moderate_no_api_key(self):
        """Raise RuntimeError when API key not configured."""
        from mascarade.integrations.mistral_capabilities import MistralClassifier

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms:
            ms.mistral_api_key = SecretStr("")

            classifier = MistralClassifier()
            with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
                await classifier.moderate(["text"])


# ---------------------------------------------------------------------------
# Router endpoints for Embeddings, Moderation, Classification
# ---------------------------------------------------------------------------


class TestMistralNewEndpoints:
    """Tests for the new FastAPI router endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client with auth disabled."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mascarade.routers.mistral_capabilities import router

        app = FastAPI()
        app.include_router(router)

        from mascarade.auth import require_auth

        app.dependency_overrides[require_auth] = lambda: None

        return TestClient(app)

    def test_embeddings_endpoint(self, client):
        """POST /v1/api/mistral/embeddings returns embeddings."""
        with patch(
            "mascarade.integrations.mistral_capabilities.MistralEmbeddings.embed",
            new_callable=AsyncMock,
            return_value={
                "data": [{"embedding": [0.1, 0.2], "index": 0}],
                "model": "mistral-embed",
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        ):
            resp = client.post(
                "/v1/api/mistral/embeddings",
                json={"texts": ["hello world"]},
            )

        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_embeddings_empty_texts(self, client):
        """400 when texts list is empty."""
        resp = client.post(
            "/v1/api/mistral/embeddings",
            json={"texts": []},
        )
        assert resp.status_code == 400

    def test_moderate_endpoint(self, client):
        """POST /v1/api/mistral/moderate returns moderation results."""
        with patch(
            "mascarade.integrations.mistral_capabilities.MistralClassifier.moderate",
            new_callable=AsyncMock,
            return_value={
                "results": [{"categories": {"sexual": False, "pii": False}}],
            },
        ):
            resp = client.post(
                "/v1/api/mistral/moderate",
                json={"inputs": ["safe text"]},
            )

        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_moderate_empty_inputs(self, client):
        """400 when inputs list is empty."""
        resp = client.post(
            "/v1/api/mistral/moderate",
            json={"inputs": []},
        )
        assert resp.status_code == 400

    def test_classify_endpoint(self, client):
        """POST /v1/api/mistral/classify returns classification results."""
        with patch(
            "mascarade.integrations.mistral_capabilities.MistralClassifier.classify",
            new_callable=AsyncMock,
            return_value={
                "results": [{"categories": {"pii": True}}],
            },
        ):
            resp = client.post(
                "/v1/api/mistral/classify",
                json={"inputs": ["email: test@example.com"]},
            )

        assert resp.status_code == 200
        assert resp.json()["results"][0]["categories"]["pii"] is True

    def test_classify_no_api_key(self, client):
        """503 when API key not configured."""
        with patch(
            "mascarade.integrations.mistral_capabilities.MistralClassifier.classify",
            new_callable=AsyncMock,
            side_effect=RuntimeError("MISTRAL_API_KEY not configured"),
        ):
            resp = client.post(
                "/v1/api/mistral/classify",
                json={"inputs": ["text"]},
            )

        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# MistralRemoteAgent.register_mcp_tools
# ---------------------------------------------------------------------------


class TestMistralRemoteAgentMCP:
    """Tests for MCP tool registration on MistralRemoteAgent."""

    @pytest.mark.asyncio
    async def test_register_mcp_tools(self):
        """register_mcp_tools sends PATCH to Mistral API."""
        from mascarade.agents.mistral_agents import MistralRemoteAgent

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("mascarade.agents.mistral_agents.settings") as ms,
            patch("httpx.AsyncClient") as mock_cls,
        ):
            ms.mistral_api_key = _FAKE_API_KEY
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            agent = MistralRemoteAgent(
                name="test-agent",
                description="test",
                system_prompt="",
                agent_id="ag:test-123",
            )
            await agent.register_mcp_tools("http://localhost:8100/v1/mcp")

        # Verify PATCH was called with correct URL and payload
        call_args = mock_client.patch.call_args
        assert "ag:test-123" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["tools"][0]["type"] == "mcp"
        assert payload["tools"][0]["mcp"]["url"] == "http://localhost:8100/v1/mcp"

    @pytest.mark.asyncio
    async def test_register_mcp_tools_no_agent_id(self):
        """Raise ValueError when agent_id is empty."""
        from mascarade.agents.mistral_agents import MistralRemoteAgent

        with patch("mascarade.agents.mistral_agents.settings") as ms:
            ms.mistral_api_key = _FAKE_API_KEY

            agent = MistralRemoteAgent(
                name="test-agent",
                description="test",
                system_prompt="",
                agent_id="",
            )
            with pytest.raises(ValueError, match="agent_id"):
                await agent.register_mcp_tools("http://localhost:8100/v1/mcp")

    @pytest.mark.asyncio
    async def test_register_mcp_tools_no_api_key(self):
        """Raise RuntimeError when API key not configured."""
        from mascarade.agents.mistral_agents import MistralRemoteAgent

        with patch("mascarade.agents.mistral_agents.settings") as ms:
            ms.mistral_api_key = SecretStr("")

            agent = MistralRemoteAgent(
                name="test-agent",
                description="test",
                system_prompt="",
                agent_id="ag:test-123",
            )
            with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
                await agent.register_mcp_tools("http://localhost:8100/v1/mcp")
