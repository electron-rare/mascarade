"""LightRAG MCP tool definitions for mascarade.

Exposes graph-augmented RAG capabilities as MCP tools:
- lightrag_query: multi-mode knowledge graph query
- lightrag_ingest: ingest documents into the graph
- lightrag_stats: graph storage statistics
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("mascarade.mcp.lightrag_mcp")

# MCP tool definitions (JSON Schema for tools/list)
LIGHTRAG_TOOLS: list[dict[str, Any]] = [
    {
        "name": "lightrag_query",
        "description": (
            "Query the LightRAG knowledge graph with multi-mode retrieval. "
            "Modes: naive (keyword), local (entity neighborhood), "
            "global (community summaries), hybrid (local+global), mix (all)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query text to search for.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["naive", "local", "global", "hybrid", "mix"],
                    "description": "Retrieval mode. Default: hybrid.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Max results to return. Default: 5.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lightrag_ingest",
        "description": (
            "Ingest a text document into the LightRAG knowledge graph. "
            "Extracts entities and relations, builds graph, indexes for retrieval."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The document text to ingest.",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata to attach.",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lightrag_stats",
        "description": "Get statistics about the LightRAG knowledge graph storage.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]


# Singleton backend instance (lazy)
_backend = None


def _get_backend():
    """Get or create the LightRAG backend singleton."""
    global _backend
    if _backend is None:
        from mascarade.rag.lightrag_backend import LightRAGBackend

        _backend = LightRAGBackend()
    return _backend


async def handle_lightrag_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch an MCP tool call to the LightRAG backend.

    Args:
        name: Tool name (lightrag_query, lightrag_ingest, lightrag_stats).
        arguments: Tool arguments from the MCP client.

    Returns:
        Tool result dict.
    """
    from mascarade.config import settings
    from mascarade.rag.lightrag_backend import LIGHTRAG_AVAILABLE

    if not settings.lightrag_enabled:
        return {"error": "LightRAG is disabled. Set LIGHTRAG_ENABLED=true to enable."}

    if not LIGHTRAG_AVAILABLE:
        return {"error": "lightrag-hku is not installed. Run: pip install lightrag-hku"}

    try:
        backend = _get_backend()

        if name == "lightrag_query":
            return await backend.query(
                text=arguments["query"],
                mode=arguments.get("mode", "hybrid"),
                top_k=arguments.get("top_k", 5),
            )
        elif name == "lightrag_ingest":
            return await backend.ingest(
                text=arguments["text"],
                metadata=arguments.get("metadata"),
            )
        elif name == "lightrag_stats":
            return await backend.get_stats()
        else:
            return {"error": f"Unknown LightRAG tool: {name}"}

    except ImportError as exc:
        return {"error": f"LightRAG dependency missing: {exc}"}
    except Exception as exc:
        logger.error("LightRAG tool %s failed: %s", name, exc)
        return {"error": str(exc)}
