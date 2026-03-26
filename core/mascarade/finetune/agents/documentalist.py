"""Documentalist agent — searches and curates datasets from HuggingFace Hub."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.finetune.documentalist")


@dataclass
class DatasetCandidate:
    dataset_id: str
    domain: str
    downloads: int = 0
    likes: int = 0
    license: str = ""
    tags: list[str] = field(default_factory=list)
    size_estimate_mb: float = 0.0
    row_count: int = 0
    languages: list[str] = field(default_factory=list)
    format: str = ""


class DocumentalistAgent:
    """Searches and curates datasets for fine-tuning.

    Runs locally (needs internet access). Verifies dataset quality,
    format compatibility, and license.

    P2P capability: ft-dataset
    """

    PREFERRED_FORMATS = {"jsonl", "parquet", "json", "csv"}
    PREFERRED_LICENSES = {
        "apache-2.0",
        "mit",
        "cc-by-4.0",
        "cc-by-sa-4.0",
        "cc0-1.0",
        "openrail",
    }

    def __init__(self, *, hf_token: str | None = None):
        self.hf_token = hf_token

    async def search_datasets(
        self,
        domain: str,
        *,
        min_downloads: int = 50,
        sort: str = "downloads",
        limit: int = 20,
        languages: list[str] | None = None,
    ) -> list[DatasetCandidate]:
        """Search HuggingFace Hub for datasets matching a domain."""
        try:
            return await self._search_via_hf_hub(
                domain,
                min_downloads=min_downloads,
                sort=sort,
                limit=limit,
                languages=languages,
            )
        except ImportError:
            logger.warning("huggingface_hub not installed, using HTTP fallback")
            return await self._search_via_http(
                domain,
                min_downloads=min_downloads,
                sort=sort,
                limit=limit,
            )

    async def _search_via_hf_hub(
        self,
        domain: str,
        *,
        min_downloads: int,
        sort: str,
        limit: int,
        languages: list[str] | None,
    ) -> list[DatasetCandidate]:
        from huggingface_hub import HfApi

        api = HfApi(token=self.hf_token)

        datasets = await asyncio.to_thread(
            lambda: list(
                api.list_datasets(
                    search=domain,
                    sort=sort,
                    limit=limit * 3,
                )
            )
        )

        candidates = []
        for d in datasets:
            if (d.downloads or 0) < min_downloads:
                continue

            tags = list(d.tags or [])
            license_tag = next((t for t in tags if t in self.PREFERRED_LICENSES), "")
            langs = []
            for t in tags:
                if t.startswith("language:"):
                    langs.append(t.split(":")[1])

            if languages and not any(l in langs for l in languages):
                continue

            candidates.append(
                DatasetCandidate(
                    dataset_id=d.id,
                    domain=domain,
                    downloads=d.downloads or 0,
                    likes=d.likes or 0,
                    license=license_tag,
                    tags=tags[:10],
                    languages=langs,
                )
            )
            if len(candidates) >= limit:
                break

        logger.info("Found %d dataset candidates for domain=%s", len(candidates), domain)
        return candidates

    async def _search_via_http(
        self,
        domain: str,
        *,
        min_downloads: int,
        sort: str,
        limit: int,
    ) -> list[DatasetCandidate]:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://huggingface.co/api/datasets",
                params={
                    "search": domain,
                    "sort": sort,
                    "direction": "-1",
                    "limit": limit,
                },
            )
            resp.raise_for_status()
            datasets = resp.json()

        return [
            DatasetCandidate(
                dataset_id=d["id"],
                domain=domain,
                downloads=d.get("downloads", 0),
                likes=d.get("likes", 0),
                tags=d.get("tags", [])[:10],
            )
            for d in datasets
            if (d.get("downloads", 0) or 0) >= min_downloads
        ][:limit]

    async def inspect_dataset(self, dataset_id: str) -> dict:
        """Get detailed info about a dataset (splits, row counts, formats)."""
        try:
            from huggingface_hub import HfApi

            api = HfApi(token=self.hf_token)
            info = await asyncio.to_thread(api.dataset_info, dataset_id)
            return {
                "dataset_id": dataset_id,
                "description": (info.description or "")[:500],
                "tags": list(info.tags or []),
                "downloads": info.downloads or 0,
                "likes": info.likes or 0,
                "card_data": dict(info.card_data) if info.card_data else {},
            }
        except Exception as e:
            logger.warning("Failed to inspect dataset %s: %s", dataset_id, e)
            return {"dataset_id": dataset_id, "error": str(e)}

    async def recommend(
        self,
        domain: str,
        *,
        top_k: int = 5,
        languages: list[str] | None = None,
    ) -> dict:
        """Full dataset search with quality ranking."""
        datasets = await self.search_datasets(domain, languages=languages)
        ranked = sorted(datasets, key=lambda d: (d.downloads * 0.7 + d.likes * 0.3), reverse=True)
        top = ranked[:top_k]

        return {
            "domain": domain,
            "languages": languages,
            "candidates": [
                {
                    "dataset_id": d.dataset_id,
                    "downloads": d.downloads,
                    "likes": d.likes,
                    "license": d.license,
                    "languages": d.languages,
                    "tags": d.tags,
                }
                for d in top
            ],
        }
