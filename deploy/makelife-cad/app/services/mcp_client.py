import asyncio
import os
import time
import httpx

KICAD_MCP_URL = os.getenv("KICAD_MCP_URL", "http://mascarade-kicad-mcp:8300")


class MCPClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=KICAD_MCP_URL, timeout=30.0
        )
        self._mutex = asyncio.Lock()
        self._tools_cache: list | None = None
        self._cache_expires: float = 0

    async def list_tools(self) -> list:
        now = time.monotonic()
        if self._tools_cache is not None and now < self._cache_expires:
            return self._tools_cache
        resp = await self._client.get("/tools")
        resp.raise_for_status()
        data = resp.json()
        self._tools_cache = data.get("result", {}).get("tools", [])
        self._cache_expires = now + 300
        return self._tools_cache

    async def call_tool(self, tool: str, args: dict) -> dict:
        async with self._mutex:
            resp = await self._client.post(
                "/mcp",
                json={
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": args},
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def health(self) -> dict:
        resp = await self._client.get("/health")
        return resp.json()


mcp_client = MCPClient()
