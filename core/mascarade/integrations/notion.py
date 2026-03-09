"""Client Notion — base de connaissances + dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from notion_client import AsyncClient

from mascarade.config import is_secret_configured, settings

_OAUTH_REFRESH_SKEW = timedelta(seconds=60)
_NOTION_VERSION = "2022-06-28"


def _normalized_auth_mode() -> str:
    mode = settings.notion_auth_mode.strip().lower()
    return mode if mode in {"api_key", "oauth_oidc"} else "api_key"


def _parse_expires_at(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized).astimezone(UTC)
    except ValueError:
        return None


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def notion_auth_configured() -> bool:
    if _normalized_auth_mode() == "api_key":
        return is_secret_configured(settings.notion_api_key)
    return bool(
        settings.notion_oauth_client_id.strip()
        and is_secret_configured(settings.notion_oauth_client_secret)
        and (
            is_secret_configured(settings.notion_oauth_access_token)
            or is_secret_configured(settings.notion_oauth_refresh_token)
        )
    )


class NotionClient:
    """Client pour interagir avec Notion comme KB et dashboard."""

    def __init__(self, api_key: str | None = None) -> None:
        self._explicit_api_key = (api_key or "").strip()
        self._client_token = ""
        self._client = AsyncClient()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if hasattr(self._client, "client") and hasattr(self._client.client, "aclose"):
            await self._client.client.aclose()

    async def _refresh_oauth_access_token(self) -> str:
        token_endpoint = settings.notion_oauth_token_endpoint.strip()
        refresh_token = settings.notion_oauth_refresh_token.strip()
        client_id = settings.notion_oauth_client_id.strip()
        client_secret = settings.notion_oauth_client_secret.strip()

        if not token_endpoint:
            raise RuntimeError("Notion OAuth token endpoint is missing")
        if not is_secret_configured(refresh_token):
            raise RuntimeError("Notion OAuth refresh token is missing")
        if not client_id:
            raise RuntimeError("Notion OAuth client id is missing")
        if not is_secret_configured(client_secret):
            raise RuntimeError("Notion OAuth client secret is missing")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                token_endpoint,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(client_id, client_secret),
                headers={
                    "Accept": "application/json",
                    "Notion-Version": _NOTION_VERSION,
                },
            )
        response.raise_for_status()
        payload = response.json()
        access_token = str(payload.get("access_token") or "").strip()
        if not is_secret_configured(access_token):
            raise RuntimeError("Notion OAuth refresh returned no access token")

        settings.notion_oauth_access_token = access_token
        refreshed_refresh_token = str(payload.get("refresh_token") or "").strip()
        if is_secret_configured(refreshed_refresh_token):
            settings.notion_oauth_refresh_token = refreshed_refresh_token

        expires_in = payload.get("expires_in")
        if isinstance(expires_in, int | float) and expires_in > 0:
            settings.notion_oauth_expires_at = _iso_utc(
                datetime.now(tz=UTC) + timedelta(seconds=int(expires_in))
            )
        else:
            settings.notion_oauth_expires_at = ""

        workspace_name = str(payload.get("workspace_name") or "").strip()
        if workspace_name:
            settings.notion_oauth_workspace_name = workspace_name

        return access_token

    async def _resolve_oauth_access_token(self) -> str:
        access_token = settings.notion_oauth_access_token.strip()
        expires_at = _parse_expires_at(settings.notion_oauth_expires_at)
        if is_secret_configured(access_token):
            if expires_at is None or expires_at > datetime.now(tz=UTC) + _OAUTH_REFRESH_SKEW:
                return access_token
        if is_secret_configured(settings.notion_oauth_refresh_token):
            return await self._refresh_oauth_access_token()
        raise RuntimeError("Notion OAuth access token is missing")

    async def _resolve_access_token(self) -> str:
        if is_secret_configured(self._explicit_api_key):
            return self._explicit_api_key
        if _normalized_auth_mode() == "api_key":
            token = settings.notion_api_key.strip()
            if not is_secret_configured(token):
                raise RuntimeError("Notion API key is missing")
            return token
        return await self._resolve_oauth_access_token()

    async def _ensure_client(self) -> AsyncClient:
        token = await self._resolve_access_token()
        if token == self._client_token:
            return self._client
        await self.close()
        self._client = AsyncClient(auth=token)
        self._client_token = token
        return self._client

    async def read_page(self, page_id: str) -> str:
        """Lire le contenu d'une page Notion comme texte brut."""
        client = await self._ensure_client()
        blocks = await client.blocks.children.list(block_id=page_id)
        return self._blocks_to_text(blocks["results"])

    async def search(self, query: str) -> list[dict]:
        """Chercher dans la base de connaissances Notion."""
        client = await self._ensure_client()
        response = await client.search(query=query)
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
        client = await self._ensure_client()
        await client.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]},
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
        client = await self._ensure_client()
        page = await client.pages.create(
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
