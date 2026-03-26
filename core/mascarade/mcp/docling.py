"""Docling MCP client — document parsing and conversion via docling-serve."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("mascarade.mcp.docling")

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class DoclingMcpClient:
    """Thin async client for docling-serve REST API.

    Exposes two MCP-style tools:
    - ``convert_url``: fetch + parse a remote document (PDF, DOCX, HTML, …)
    - ``convert_text``: parse raw HTML/markdown text
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public tools
    # ------------------------------------------------------------------

    async def convert_url(
        self,
        url: str,
        *,
        output_format: str = "markdown",
        ocr: bool = False,
    ) -> dict[str, Any]:
        """Fetch and parse a remote document.

        Args:
            url: HTTP/HTTPS URL of the document to parse.
            output_format: ``"markdown"`` (default) or ``"json"``.
            ocr: Enable OCR for scanned PDFs (slower).

        Returns:
            Dict with ``content`` (str) and ``metadata`` keys.
        """
        payload: dict[str, Any] = {
            "http_source": {"url": url},
            "options": {
                "to_formats": [output_format],
                "ocr": {"enabled": ocr},
            },
        }
        return await self._convert(payload, output_format)

    async def convert_text(
        self,
        content: str,
        *,
        mime_type: str = "text/html",
        output_format: str = "markdown",
    ) -> dict[str, Any]:
        """Parse raw text content (HTML, markdown, etc.).

        Args:
            content: Raw text to parse.
            mime_type: MIME type hint (``text/html``, ``text/markdown``, …).
            output_format: ``"markdown"`` (default) or ``"json"``.

        Returns:
            Dict with ``content`` (str) and ``metadata`` keys.
        """
        import base64

        encoded = base64.b64encode(content.encode()).decode()
        payload: dict[str, Any] = {
            "inline_source": {"base64_string": encoded, "media_type": mime_type},
            "options": {"to_formats": [output_format]},
        }
        return await self._convert(payload, output_format)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _convert(self, payload: dict[str, Any], output_format: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base_url}/v1alpha/convert/source",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # docling-serve wraps results under `document.{format}_content`
        document = data.get("document", {})
        content = (
            document.get(f"{output_format}_content")
            or document.get("md_content")
            or document.get("text_content")
            or ""
        )
        metadata = {
            k: v
            for k, v in document.items()
            if k not in {"md_content", "json_content", "text_content"}
        }
        return {"content": content, "metadata": metadata}


def get_client() -> DoclingMcpClient | None:
    """Return a configured client if DOCLING_URL is set, else None."""
    url = os.getenv("DOCLING_URL", "")
    if not url:
        return None
    return DoclingMcpClient(url)
