"""Provider-aware knowledge base integration facade.

Runtime selection supports self-hosted providers plus the kxkm RAG bridge.
"""

from __future__ import annotations

import json
import socket
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from mascarade.config import is_secret_configured, settings

_DEFAULT_MEMOS_VISIBILITY = "PRIVATE"
_DOCMOST_LOGIN_TIMEOUT_S = 20.0
_HTTP_TIMEOUT_S = 20.0
_DOCMOST_SESSION_SKEW = timedelta(seconds=30)


def normalized_knowledge_base_provider() -> str:
    provider = settings.knowledge_base_provider.strip().lower()
    return provider if provider in {"memos", "docmost", "kxkm"} else "memos"


def knowledge_base_provider_label(provider: str | None = None) -> str:
    selected = provider or normalized_knowledge_base_provider()
    if selected == "memos":
        return "Memos"
    if selected == "docmost":
        return "Docmost"
    if selected == "kxkm":
        return "kxkm"
    return "Knowledge Base"


def knowledge_base_smoke_page_id() -> str:
    return settings.knowledge_base_smoke_page_id.strip()


def knowledge_base_auth_configured(provider: str | None = None) -> bool:
    selected = provider or normalized_knowledge_base_provider()
    if selected == "memos":
        return bool(
            settings.memos_base_url.strip() and is_secret_configured(settings.memos_access_token)
        )
    if selected == "docmost":
        return bool(
            settings.docmost_base_url.strip()
            and settings.docmost_email.strip()
            and is_secret_configured(settings.docmost_password)
        )
    if selected == "kxkm":
        return bool(settings.kxkm_rag_url.strip())
    return False


def knowledge_base_status_detail(provider: str | None = None) -> str:
    selected = provider or normalized_knowledge_base_provider()
    label = knowledge_base_provider_label(selected)
    if selected == "memos":
        return f"{label} non configure (MEMOS_BASE_URL ou MEMOS_ACCESS_TOKEN manquant)"
    if selected == "docmost":
        return (
            f"{label} non configure "
            "(DOCMOST_BASE_URL, DOCMOST_EMAIL ou DOCMOST_PASSWORD manquant)"
        )
    if selected == "kxkm":
        return f"{label} non configure (KXKM_RAG_URL manquant)"
    return f"{label} non configure (provider actif non supporte)"


class KnowledgeBaseAdapter(ABC):
    provider: str
    label: str

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def read_page(self, page_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def append_to_page(self, page_id: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_page(self, parent_id: str, title: str, content: str = "") -> str:
        raise NotImplementedError


def _extract_first_line_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        normalized = line.strip().lstrip("#").strip()
        if normalized:
            return normalized[:140]
    return fallback


def _strip_memos_name(name: str) -> str:
    normalized = name.strip()
    if normalized.startswith("memos/"):
        return normalized[len("memos/") :]
    return normalized


def _as_memos_name(name: str) -> str:
    normalized = _strip_memos_name(name)
    if not normalized:
        raise RuntimeError("Memos memo id is missing")
    return f"memos/{normalized}"


def _json_field_mask(fields: list[str]) -> str:
    return ",".join(field for field in fields if field)


def _memos_public_url() -> str:
    public_url = settings.memos_public_url.strip().rstrip("/")
    if public_url:
        return public_url
    return settings.memos_base_url.strip().rstrip("/")


def _url_host_resolves(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.hostname:
        return False
    try:
        socket.getaddrinfo(parsed.hostname, parsed.port or 80)
    except OSError:
        return False
    return True


def _memos_api_base_url() -> str:
    internal_url = settings.memos_base_url.strip().rstrip("/")
    public_url = settings.memos_public_url.strip().rstrip("/")
    if internal_url and _url_host_resolves(internal_url):
        return internal_url
    if public_url and _url_host_resolves(public_url):
        return public_url
    return internal_url or public_url


class MemosClient(KnowledgeBaseAdapter):
    provider = "memos"
    label = "Memos"

    def __init__(self) -> None:
        base_url = _memos_api_base_url()
        if not base_url:
            raise RuntimeError("Memos base URL is missing")
        token = settings.memos_access_token.strip()
        if not is_secret_configured(token):
            raise RuntimeError("Memos access token is missing")
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=_HTTP_TIMEOUT_S,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        response = await self._client.get(
            "/api/v1/memos",
            params={
                "page_size": max(1, min(limit, 100)),
                "order_by": "update_time desc",
                "filter": f"content.contains({json.dumps(query.strip())})",
            },
        )
        response.raise_for_status()
        payload = response.json()
        memos = payload.get("memos") or []
        results: list[dict[str, Any]] = []
        for memo in memos[:limit]:
            name = str(memo.get("name") or "").strip()
            memo_id = _strip_memos_name(name)
            content = str(memo.get("content") or "")
            results.append(
                {
                    "id": memo_id,
                    "title": _extract_first_line_title(content, memo_id or "Untitled memo"),
                    "url": f"{_memos_public_url()}/memos/{memo_id}" if memo_id else "",
                    "provider": self.provider,
                }
            )
        return results

    async def read_page(self, page_id: str) -> str:
        response = await self._client.get(f"/api/v1/{_as_memos_name(page_id)}")
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("content") or "")

    async def append_to_page(self, page_id: str, content: str) -> None:
        current = await self._client.get(f"/api/v1/{_as_memos_name(page_id)}")
        current.raise_for_status()
        payload = current.json()
        current_content = str(payload.get("content") or "")
        next_content = f"{current_content.rstrip()}\n\n{content.strip()}\n"
        response = await self._client.patch(
            f"/api/v1/{_as_memos_name(page_id)}",
            json={
                "memo": {
                    "name": _as_memos_name(page_id),
                    "content": next_content,
                },
                "updateMask": "content",
            },
        )
        response.raise_for_status()

    async def create_page(self, parent_id: str, title: str, content: str = "") -> str:
        memo_content = f"# {title.strip()}\n\n{content.strip()}".strip()
        response = await self._client.post(
            "/api/v1/memos",
            json={
                "memo": {
                    "content": memo_content,
                    "visibility": settings.memos_default_visibility.strip().upper()
                    or _DEFAULT_MEMOS_VISIBILITY,
                }
            },
        )
        response.raise_for_status()
        payload = response.json()
        return _strip_memos_name(str(payload.get("name") or ""))


def _docmost_page_url(base_url: str, page: dict[str, Any]) -> str:
    slug_id = str(page.get("slugId") or "").strip()
    title = str(page.get("title") or "").strip()
    space = page.get("space") or {}
    space_slug = str(space.get("slug") or "").strip()
    title_slug = (
        title.lower().replace("/", "-").replace(" ", "-").replace("--", "-").strip("-")
        or "untitled"
    )[:90]
    if not slug_id:
        return ""
    if space_slug:
        return f"{base_url}/s/{space_slug}/p/{title_slug}-{slug_id}"
    return f"{base_url}/p/{title_slug}-{slug_id}"


class DocmostClient(KnowledgeBaseAdapter):
    provider = "docmost"
    label = "Docmost"

    def __init__(self) -> None:
        base_url = settings.docmost_base_url.strip().rstrip("/")
        if not base_url:
            raise RuntimeError("Docmost base URL is missing")
        if not settings.docmost_email.strip():
            raise RuntimeError("Docmost email is missing")
        if not is_secret_configured(settings.docmost_password):
            raise RuntimeError("Docmost password is missing")
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Accept": "application/json"},
            timeout=_HTTP_TIMEOUT_S,
        )
        self._session_started_at: datetime | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def _ensure_session(self) -> None:
        if (
            self._session_started_at
            and self._session_started_at > datetime.now(tz=UTC) - _DOCMOST_SESSION_SKEW
        ):
            return
        response = await self._client.post(
            "/api/auth/login",
            json={
                "email": settings.docmost_email.strip(),
                "password": settings.docmost_password.strip(),
            },
        )
        response.raise_for_status()
        self._session_started_at = datetime.now(tz=UTC)

    async def _page_info(self, page_id: str, *, format: str = "markdown") -> dict[str, Any]:
        await self._ensure_session()
        response = await self._client.post(
            "/api/pages/info",
            json={
                "pageId": page_id,
                "includeSpace": True,
                "includeContent": True,
                "format": format,
            },
        )
        response.raise_for_status()
        return response.json()

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[dict[str, Any]]:
        await self._ensure_session()
        if not query.strip():
            return []
        payload: dict[str, Any] = {"query": query.strip(), "limit": max(1, min(limit, 50))}
        if settings.docmost_space_id.strip():
            payload["spaceId"] = settings.docmost_space_id.strip()
        response = await self._client.post("/api/search", json=payload)
        response.raise_for_status()
        data = response.json()
        items = data.get("items") or []
        results: list[dict[str, Any]] = []
        for item in items[:limit]:
            page_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "").strip() or page_id or "Untitled page"
            results.append(
                {
                    "id": page_id,
                    "title": title,
                    "url": _docmost_page_url(self._base_url, item),
                    "provider": self.provider,
                }
            )
        return results

    async def read_page(self, page_id: str) -> str:
        page = await self._page_info(page_id, format="markdown")
        return str(page.get("content") or "")

    async def append_to_page(self, page_id: str, content: str) -> None:
        await self._ensure_session()
        response = await self._client.post(
            "/api/pages/update",
            json={
                "pageId": page_id,
                "content": content.strip(),
                "operation": "append",
                "format": "markdown",
            },
        )
        response.raise_for_status()

    async def create_page(self, parent_id: str, title: str, content: str = "") -> str:
        parent_page = await self._page_info(parent_id, format="json")
        space_id = str(parent_page.get("spaceId") or settings.docmost_space_id).strip()
        if not space_id:
            raise RuntimeError("Docmost space ID is missing and could not be inferred from parent")
        await self._ensure_session()
        response = await self._client.post(
            "/api/pages/create",
            json={
                "parentPageId": parent_id,
                "spaceId": space_id,
                "title": title.strip(),
                "content": content,
                "format": "markdown",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("id") or "").strip()


def _normalize_scope(
    *,
    project_id: str | None = None,
    federation_scope: list[str] | tuple[str, ...] | None = None,
    knowledge_scope: str = "project",
) -> tuple[str, list[str], str]:
    normalized_project = (project_id or settings.mascarade_project_id).strip() or "default"
    normalized_scope = (knowledge_scope or "project").strip().lower() or "project"
    if normalized_scope not in {"project", "federated"}:
        raise RuntimeError(f"Unsupported knowledge scope: {knowledge_scope}")

    cleaned_federation = [
        item.strip()
        for item in (federation_scope or [])
        if str(item).strip()
    ]
    if normalized_scope == "project":
        cleaned_federation = [normalized_project]
    elif not cleaned_federation:
        raise RuntimeError("federation_scope is required when knowledge_scope is federated")
    elif normalized_project not in cleaned_federation:
        cleaned_federation = [normalized_project, *cleaned_federation]

    return normalized_project, list(dict.fromkeys(cleaned_federation)), normalized_scope


class KxkmClient(KnowledgeBaseAdapter):
    provider = "kxkm"
    label = "kxkm"

    def __init__(self) -> None:
        base_url = settings.kxkm_rag_url.strip().rstrip("/")
        if not base_url:
            raise RuntimeError("kxkm RAG base URL is missing")
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Accept": "application/json"},
            timeout=settings.kxkm_timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[dict[str, Any]]:
        normalized_project, normalized_federation, normalized_scope = _normalize_scope(
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )
        if not query.strip():
            return []

        response = await self._client.post(
            "/api/v2/rag/search",
            headers={
                "x-mascarade-project-id": normalized_project,
                "x-mascarade-knowledge-scope": normalized_scope,
                "x-mascarade-federation-scope": ",".join(normalized_federation),
            },
            json={
                "query": query.strip(),
                "limit": max(1, min(limit, 50)),
                "project_id": normalized_project,
                "federation_scope": normalized_federation,
                "knowledge_scope": normalized_scope,
            },
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        items = data.get("results") or []
        results: list[dict[str, Any]] = []
        for index, item in enumerate(items[:limit]):
            if not isinstance(item, dict):
                item = {"text": str(item)}
            text = str(item.get("text") or item.get("content") or item.get("chunk") or "").strip()
            title = _extract_first_line_title(text, f"kxkm-{index + 1}")
            results.append(
                {
                    "id": str(item.get("id") or item.get("chunk_id") or f"kxkm-{index + 1}"),
                    "title": title,
                    "url": str(item.get("url") or item.get("source_url") or ""),
                    "provider": self.provider,
                    "text": text,
                    "score": item.get("score"),
                    "metadata": {
                        "project_id": normalized_project,
                        "knowledge_scope": normalized_scope,
                        "federation_scope": normalized_federation,
                        **{
                            key: value
                            for key, value in item.items()
                            if key not in {"id", "chunk_id", "text", "content", "chunk", "url", "source_url", "score"}
                        },
                    },
                }
            )
        return results

    async def read_page(self, page_id: str) -> str:
        raise RuntimeError("kxkm knowledge provider is search-only")

    async def append_to_page(self, page_id: str, content: str) -> None:
        raise RuntimeError("kxkm knowledge provider is search-only")

    async def create_page(self, parent_id: str, title: str, content: str = "") -> str:
        raise RuntimeError("kxkm knowledge provider is search-only")


class KnowledgeBaseClient(KnowledgeBaseAdapter):
    def __init__(self, provider: str | None = None) -> None:
        self.provider = provider or normalized_knowledge_base_provider()
        self.label = knowledge_base_provider_label(self.provider)
        if self.provider == "memos":
            self._client: KnowledgeBaseAdapter = MemosClient()
        elif self.provider == "docmost":
            self._client = DocmostClient()
        elif self.provider == "kxkm":
            self._client = KxkmClient()
        else:
            raise RuntimeError(f"Unsupported knowledge base provider: {self.provider}")

    async def close(self) -> None:
        await self._client.close()

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> list[dict[str, Any]]:
        return await self._client.search(
            query,
            limit=limit,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )

    async def read_page(self, page_id: str) -> str:
        return await self._client.read_page(page_id)

    async def append_to_page(self, page_id: str, content: str) -> None:
        await self._client.append_to_page(page_id, content)

    async def create_page(self, parent_id: str, title: str, content: str = "") -> str:
        return await self._client.create_page(parent_id, title, content)
