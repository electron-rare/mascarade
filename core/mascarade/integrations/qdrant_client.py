"""Client Qdrant — vector database for knowledge base."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from mascarade.config import settings

logger = logging.getLogger(__name__)


class QdrantClient:
    """Client pour interagir avec une instance Qdrant externe."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.qdrant_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    # --- Collections ---

    async def list_collections(self) -> dict[str, Any]:
        """Lister toutes les collections disponibles."""
        resp = await self._client.get("/collections")
        resp.raise_for_status()
        return resp.json()

    async def get_collection(self, collection_name: str) -> dict[str, Any]:
        """Obtenir les informations d'une collection."""
        resp = await self._client.get(f"/collections/{collection_name}")
        resp.raise_for_status()
        return resp.json()

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "Cosine",
        on_disk_payload: bool = False,
    ) -> dict[str, Any]:
        """Créer une nouvelle collection."""
        payload = {
            "vectors": {
                "size": vector_size,
                "distance": distance,
                "on_disk": on_disk_payload,
            }
        }
        resp = await self._client.put(f"/collections/{collection_name}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_collection(self, collection_name: str) -> dict[str, Any]:
        """Supprimer une collection."""
        resp = await self._client.delete(f"/collections/{collection_name}")
        resp.raise_for_status()
        return resp.json()

    async def collection_exists(self, collection_name: str) -> bool:
        """Vérifier si une collection existe."""
        try:
            await self.get_collection(collection_name)
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    # --- Points (vectors) ---

    async def upsert_points(
        self,
        collection_name: str,
        points: list[dict[str, Any]],
        wait: bool = True,
    ) -> dict[str, Any]:
        """Insérer ou mettre à jour des points dans une collection."""
        payload = {"points": points}
        params = {"wait": "true" if wait else "false"}
        resp = await self._client.put(
            f"/collections/{collection_name}/points",
            json=payload,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_point(
        self,
        collection_name: str,
        point_id: str | int,
        with_payload: bool = True,
        with_vector: bool = False,
    ) -> dict[str, Any]:
        """Récupérer un point par son ID."""
        params = {
            "with_payload": str(with_payload).lower(),
            "with_vector": str(with_vector).lower(),
        }
        resp = await self._client.get(
            f"/collections/{collection_name}/points/{point_id}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_points(
        self,
        collection_name: str,
        points: list[str | int],
        wait: bool = True,
    ) -> dict[str, Any]:
        """Supprimer des points d'une collection."""
        payload = {"points": points}
        params = {"wait": "true" if wait else "false"}
        resp = await self._client.post(
            f"/collections/{collection_name}/points/delete",
            json=payload,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def scroll_points(
        self,
        collection_name: str,
        limit: int = 10,
        offset: str | int | None = None,
        with_payload: bool = True,
        with_vector: bool = False,
    ) -> dict[str, Any]:
        """Parcourir les points d'une collection."""
        payload = {
            "limit": limit,
            "with_payload": with_payload,
            "with_vector": with_vector,
        }
        if offset is not None:
            payload["offset"] = offset
        resp = await self._client.post(
            f"/collections/{collection_name}/points/scroll",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    # --- Search ---

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        with_payload: bool = True,
        with_vector: bool = False,
        filter_conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Rechercher les points les plus similaires à un vecteur."""
        payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": with_payload,
            "with_vector": with_vector,
        }
        if score_threshold is not None:
            payload["score_threshold"] = score_threshold
        if filter_conditions:
            payload["filter"] = filter_conditions
        resp = await self._client.post(
            f"/collections/{collection_name}/points/search",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def recommend(
        self,
        collection_name: str,
        positive: list[str | int],
        negative: list[str | int] | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
        with_payload: bool = True,
        with_vector: bool = False,
        filter_conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Recommander des points similaires basés sur des exemples positifs/négatifs."""
        payload = {
            "positive": positive,
            "limit": limit,
            "with_payload": with_payload,
            "with_vector": with_vector,
        }
        if negative:
            payload["negative"] = negative
        if score_threshold is not None:
            payload["score_threshold"] = score_threshold
        if filter_conditions:
            payload["filter"] = filter_conditions
        resp = await self._client.post(
            f"/collections/{collection_name}/points/recommend",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    # --- Cluster / Health ---

    async def health_check(self) -> dict[str, Any]:
        """Vérifier l'état de santé du cluster Qdrant."""
        resp = await self._client.get("/")
        resp.raise_for_status()
        return resp.json()

    async def get_cluster_status(self) -> dict[str, Any]:
        """Obtenir le statut du cluster."""
        resp = await self._client.get("/cluster")
        resp.raise_for_status()
        return resp.json()

    # --- Utilitaires ---

    @staticmethod
    def create_point(
        point_id: str | int | None = None,
        vector: list[float] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Créer un point formaté pour Qdrant."""
        if point_id is None:
            point_id = str(uuid.uuid4())
        point = {"id": point_id}
        if vector is not None:
            point["vector"] = vector
        if payload:
            point["payload"] = payload
        return point

    async def close(self) -> None:
        """Fermer la connexion HTTP."""
        await self._client.aclose()
