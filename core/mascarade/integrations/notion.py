"""Client Notion — base de connaissances + dashboard."""

from __future__ import annotations

from notion_client import AsyncClient

from mascarade.config import settings


class NotionClient:
    """Client pour interagir avec Notion comme KB et dashboard."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncClient(auth=api_key or settings.notion_api_key)

    async def read_page(self, page_id: str) -> str:
        """Lire le contenu d'une page Notion comme texte brut."""
        blocks = await self._client.blocks.children.list(block_id=page_id)
        return self._blocks_to_text(blocks["results"])

    async def search(self, query: str) -> list[dict]:
        """Chercher dans la base de connaissances Notion."""
        response = await self._client.search(query=query)
        return [
            {
                "id": page["id"],
                "title": self._extract_title(page),
                "url": page.get("url", ""),
            }
            for page in response["results"]
            if page["object"] == "page"
        ]

    async def append_to_page(self, page_id: str, content: str) -> None:
        """Ajouter du contenu à une page (logs, résultats)."""
        await self._client.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ],
        )

    async def create_page(
        self,
        parent_id: str,
        title: str,
        content: str = "",
    ) -> str:
        """Créer une nouvelle page dans Notion."""
        page = await self._client.pages.create(
            parent={"page_id": parent_id},
            properties={
                "title": {"title": [{"text": {"content": title}}]},
            },
        )
        if content:
            await self.append_to_page(page["id"], content)
        return page["id"]

    @staticmethod
    def _blocks_to_text(blocks: list[dict]) -> str:
        """Convertir des blocs Notion en texte brut."""
        parts = []
        for block in blocks:
            block_type = block.get("type", "")
            block_data = block.get(block_type, {})
            rich_texts = block_data.get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_texts)
            if text:
                parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def _extract_title(page: dict) -> str:
        """Extraire le titre d'une page Notion."""
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)
        return ""
