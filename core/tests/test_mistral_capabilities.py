"""Tests for Mistral Document AI and Audio Transcription capabilities."""

from __future__ import annotations

import tempfile
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

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms, \
             patch("httpx.AsyncClient") as mock_cls:
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

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms, \
             patch("httpx.AsyncClient") as mock_cls:
            ms.mistral_api_key = _FAKE_API_KEY
            ms.mistral_default_model = "mistral-large-latest"
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=mock_post)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            doc_ai = MistralDocumentAI()
            result = await doc_ai.process_document(
                str(pdf_file), prompt="What is the total?"
            )

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
        from mascarade.integrations.mistral_capabilities import MistralAudioTranscription

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "text": "Bonjour le monde",
        }

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms, \
             patch("httpx.AsyncClient") as mock_cls:
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
        from mascarade.integrations.mistral_capabilities import MistralAudioTranscription

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"text": "Transcription OK"}

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms, \
             patch("httpx.AsyncClient") as mock_cls:
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
        from mascarade.integrations.mistral_capabilities import MistralAudioTranscription

        transcriber = MistralAudioTranscription()
        with pytest.raises(FileNotFoundError):
            await transcriber.transcribe("/nonexistent/audio.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_no_api_key(self):
        """Raise RuntimeError when API key not configured."""
        from mascarade.integrations.mistral_capabilities import MistralAudioTranscription

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms:
            ms.mistral_api_key = SecretStr("")

            transcriber = MistralAudioTranscription()
            with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
                await transcriber.transcribe_bytes(
                    b"data", filename="test.wav"
                )

    @pytest.mark.asyncio
    async def test_transcribe_with_diarize(self):
        """Diarize flag is sent in the request."""
        from mascarade.integrations.mistral_capabilities import MistralAudioTranscription

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "text": "Speaker 1: hello. Speaker 2: hi.",
        }

        with patch("mascarade.integrations.mistral_capabilities.settings") as ms, \
             patch("httpx.AsyncClient") as mock_cls:
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
        from fastapi.testclient import TestClient
        from mascarade.routers.mistral_capabilities import router
        from fastapi import FastAPI

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
            return_value={"pages": [{"markdown": "content"}], "model": "mistral-ocr-latest"},
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
