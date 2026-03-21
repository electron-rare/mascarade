"""Mistral Document AI (OCR) and Audio Transcription capabilities.

Uses the Mistral API endpoints:
- POST /v1/ocr — OCR and document understanding (model: mistral-ocr-latest)
- POST /v1/audio/transcriptions — Audio transcription (model: voxtral-mini-latest)

Reference:
- https://docs.mistral.ai/capabilities/document_ai
- https://docs.mistral.ai/capabilities/audio_transcription
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from mascarade.config import is_secret_configured, secret_value, settings

logger = logging.getLogger("mascarade.integrations.mistral_capabilities")

_OCR_MODEL = "mistral-ocr-latest"
_TRANSCRIPTION_MODEL = "voxtral-mini-latest"
_API_BASE = "https://api.mistral.ai/v1"
_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


def _get_api_key() -> str:
    """Resolve the Mistral API key or raise."""
    api_key = secret_value(settings.mistral_api_key).strip()
    if not is_secret_configured(api_key):
        raise RuntimeError("MISTRAL_API_KEY not configured")
    return api_key


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
    }


# ---------------------------------------------------------------------------
# Document AI
# ---------------------------------------------------------------------------

class MistralDocumentAI:
    """Mistral Document AI -- OCR and document understanding.

    Wraps the ``POST /v1/ocr`` endpoint using *mistral-ocr-latest*.
    Supports PDF, images (PNG, JPEG, AVIF), PPTX, DOCX.
    """

    async def process_document(
        self,
        file_path: str,
        *,
        prompt: str = "",
        include_image_base64: bool = False,
        table_format: str | None = None,
    ) -> dict[str, Any]:
        """Extract text from a document and optionally answer a question.

        Parameters
        ----------
        file_path:
            Local path to a PDF, image, or office document.
        prompt:
            Optional question to answer about the document. When provided the
            OCR result is sent as context to the chat endpoint for Q&A.
        include_image_base64:
            Whether to include base64 image data in the OCR response.
        table_format:
            Table output format: ``None``, ``"markdown"``, or ``"html"``.

        Returns
        -------
        dict with ``pages`` (list of page objects) and optional ``answer``
        when *prompt* is provided.
        """
        api_key = _get_api_key()
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        b64 = base64.standard_b64encode(path.read_bytes()).decode()

        # Choose document type based on MIME
        if mime.startswith("image/"):
            document = {
                "type": "image_url",
                "image_url": f"data:{mime};base64,{b64}",
            }
        else:
            document = {
                "type": "document_url",
                "document_url": f"data:{mime};base64,{b64}",
            }

        payload: dict[str, Any] = {
            "model": _OCR_MODEL,
            "document": document,
            "include_image_base64": include_image_base64,
        }
        if table_format is not None:
            payload["table_format"] = table_format

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_API_BASE}/ocr",
                json=payload,
                headers={**_auth_headers(api_key), "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            ocr_result = resp.json()

        logger.info(
            "OCR processed %s — %d page(s)",
            path.name,
            len(ocr_result.get("pages", [])),
        )

        if not prompt:
            return ocr_result

        # Document Q&A: send OCR markdown as context to chat
        pages_md = "\n\n---\n\n".join(
            p.get("markdown", "") for p in ocr_result.get("pages", [])
        )
        answer = await self._chat_qa(api_key, pages_md, prompt)
        ocr_result["answer"] = answer
        return ocr_result

    async def ocr(self, image_path: str) -> str:
        """Extract text from an image using Mistral OCR.

        Returns the concatenated markdown text of all pages.
        """
        result = await self.process_document(image_path)
        pages = result.get("pages", [])
        return "\n\n".join(p.get("markdown", "") for p in pages)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _chat_qa(api_key: str, document_text: str, question: str) -> str:
        """Ask a question about extracted text via chat completions."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a document analysis assistant. "
                    "Answer the user's question based on the document text provided."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Document text:\n\n{document_text}\n\n---\n\nQuestion: {question}"
                ),
            },
        ]
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_API_BASE}/chat/completions",
                json={
                    "model": settings.mistral_default_model,
                    "messages": messages,
                    "temperature": 0.2,
                },
                headers={**_auth_headers(api_key), "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""


# ---------------------------------------------------------------------------
# Audio Transcription
# ---------------------------------------------------------------------------

class MistralAudioTranscription:
    """Mistral Audio Transcription -- speech-to-text.

    Wraps the ``POST /v1/audio/transcriptions`` endpoint using
    *voxtral-mini-latest*.
    """

    async def transcribe(
        self,
        audio_path: str,
        *,
        language: str = "fr",
        timestamp_granularities: list[str] | None = None,
        diarize: bool = False,
    ) -> dict[str, Any]:
        """Transcribe a local audio file to text.

        Parameters
        ----------
        audio_path:
            Path to audio file (mp3, wav, m4a, flac, ogg, webm ...).
        language:
            BCP-47 language code (default ``"fr"``).
        timestamp_granularities:
            Optional list: ``["segment"]`` and/or ``["word"]``.
        diarize:
            Enable speaker diarization.

        Returns
        -------
        dict with ``text`` and optional ``segments`` / ``words``.
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio_bytes = path.read_bytes()
        return await self.transcribe_bytes(
            audio_bytes,
            filename=path.name,
            language=language,
            timestamp_granularities=timestamp_granularities,
            diarize=diarize,
        )

    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str = "audio.wav",
        language: str = "fr",
        timestamp_granularities: list[str] | None = None,
        diarize: bool = False,
    ) -> dict[str, Any]:
        """Transcribe raw audio bytes to text.

        Parameters
        ----------
        audio_bytes:
            Raw audio data.
        filename:
            Filename hint for the audio (used to infer MIME type).
        language:
            BCP-47 language code.
        timestamp_granularities:
            Optional list: ``["segment"]`` and/or ``["word"]``.
        diarize:
            Enable speaker diarization.
        """
        api_key = _get_api_key()
        mime = mimetypes.guess_type(filename)[0] or "audio/wav"

        # Build multipart form
        files = {
            "file": (filename, audio_bytes, mime),
        }
        data: dict[str, Any] = {
            "model": _TRANSCRIPTION_MODEL,
        }
        if language:
            data["language"] = language
        if diarize:
            data["diarize"] = "true"
        if timestamp_granularities:
            for gran in timestamp_granularities:
                data.setdefault("timestamp_granularities[]", [])
                # httpx handles list values in data as repeated keys
            data["timestamp_granularities[]"] = timestamp_granularities

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_API_BASE}/audio/transcriptions",
                files=files,
                data=data,
                headers=_auth_headers(api_key),
            )
            resp.raise_for_status()
            result = resp.json()

        logger.info(
            "Transcription completed — %d chars, file=%s",
            len(result.get("text", "")),
            filename,
        )
        return result
