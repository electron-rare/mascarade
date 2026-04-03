from app.services.mcp_client import mcp_client
from app.services.ai_assistant import ai_assistant


class ComponentSearch:
    async def search(self, query: str, limit: int = 10) -> dict:
        jlcpcb = await self._search_jlcpcb(query, limit)
        datasheets = await self._search_rag(query)
        return {
            "query": query,
            "jlcpcb": jlcpcb,
            "datasheets": datasheets,
        }

    async def _search_jlcpcb(
        self, query: str, limit: int
    ) -> list:
        try:
            result = await mcp_client.call_tool(
                "search_jlcpcb_parts",
                {"query": query, "limit": limit},
            )
            content = result.get("result", {})
            return content.get("content", [])
        except Exception:
            return []

    async def _search_rag(self, query: str) -> list:
        try:
            resp = await ai_assistant._rag.post(
                "/v1/api/rag/search",
                json={
                    "query": query,
                    "collection": "datasheets",
                    "top_k": 5,
                },
            )
            if resp.status_code == 200:
                return resp.json().get("results", [])
        except Exception:
            return []


component_search = ComponentSearch()
