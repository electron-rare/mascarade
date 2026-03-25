"""MCP tool wrapper for SearXNG web search.

Allows mascarade agents to search the web via the self-hosted
SearXNG instance.

Requires env var:
  SEARXNG_URL — e.g. http://mascarade-searxng:8080
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("mascarade.mcp.searxng")

_DEFAULT_TIMEOUT = 15.0


class SearXNGMcpClient:
    """MCP-compatible client for SearXNG web search."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.getenv("SEARXNG_URL", "")).rstrip("/")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    # ------------------------------------------------------------------
    # Tool: web_search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        categories: str = "general",
        language: str = "fr",
        limit: int = 10,
    ) -> list[dict]:
        """Search the web via SearXNG.

        Args:
            query: Search query.
            categories: Comma-separated categories (general, science, it, files, etc.)
            language: Language code (fr, en, etc.)
            limit: Max results.

        Returns list of {title, url, content, engine}.
        """
        if not self.is_configured:
            return []

        params = {
            "q": query,
            "format": "json",
            "categories": categories,
            "language": language,
            "pageno": 1,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/search",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])[:limit]
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "engine": r.get("engine", ""),
            }
            for r in results
        ]

    # ------------------------------------------------------------------
    # Tool: search_and_summarize (for agent use)
    # ------------------------------------------------------------------

    async def search_text(
        self,
        query: str,
        *,
        limit: int = 5,
        language: str = "fr",
    ) -> str:
        """Search and return results as formatted text for LLM context.

        Returns a string suitable for injection into an LLM prompt.
        """
        results = await self.search(query, limit=limit, language=language)
        if not results:
            return f"Aucun resultat pour: {query}"

        lines = [f"Resultats de recherche pour: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. [{r['title']}]({r['url']})")
            if r["content"]:
                lines.append(f"   {r['content'][:200]}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # MCP tool definitions
    # ------------------------------------------------------------------

    @staticmethod
    def tool_definitions() -> list[dict]:
        """Return MCP tool definitions for SearXNG."""
        return [
            {
                "name": "web_search",
                "description": "Search the web using SearXNG (self-hosted, private, no tracking)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "categories": {
                            "type": "string",
                            "default": "general",
                            "description": "Categories: general, science, it, files, images, news",
                        },
                        "language": {"type": "string", "default": "fr"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "web_search_text",
                "description": "Search the web and return formatted text for LLM context injection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                        "language": {"type": "string", "default": "fr"},
                    },
                    "required": ["query"],
                },
            },
        ]
