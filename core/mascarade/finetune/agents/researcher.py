"""Researcher agent — searches HuggingFace Hub for base models and papers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.finetune.researcher")

ALLOWED_LICENSES = {"apache-2.0", "mit", "cc-by-4.0", "cc-by-sa-4.0", "openrail", "llama3"}


@dataclass
class ModelCandidate:
    model_id: str
    task: str
    downloads: int = 0
    likes: int = 0
    license: str = ""
    tags: list[str] = field(default_factory=list)
    size_estimate_gb: float = 0.0
    paper_refs: list[str] = field(default_factory=list)


@dataclass
class PaperResult:
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    summary: str = ""


class ResearcherAgent:
    """Searches HuggingFace Hub for base models and arXiv for papers.

    This agent runs locally (needs internet access) and produces
    a ranked list of model candidates for a given task.

    P2P capability: ft-research
    """

    def __init__(self, *, hf_token: str | None = None):
        self.hf_token = hf_token

    async def search_base_models(
        self,
        task: str,
        *,
        max_size_gb: float = 4.0,
        min_downloads: int = 100,
        sort: str = "downloads",
        limit: int = 20,
    ) -> list[ModelCandidate]:
        """Search HuggingFace Hub for models matching a task.

        Uses the huggingface_hub Python library for reliable searching.
        Falls back to the HF MCP tools if available.
        """
        try:
            return await self._search_via_hf_hub(
                task, max_size_gb=max_size_gb, min_downloads=min_downloads,
                sort=sort, limit=limit,
            )
        except ImportError:
            logger.warning("huggingface_hub not installed, using HTTP fallback")
            return await self._search_via_http(
                task, max_size_gb=max_size_gb, min_downloads=min_downloads,
                sort=sort, limit=limit,
            )

    async def _search_via_hf_hub(
        self, task: str, *, max_size_gb: float, min_downloads: int,
        sort: str, limit: int,
    ) -> list[ModelCandidate]:
        from huggingface_hub import HfApi
        api = HfApi(token=self.hf_token)

        models = await asyncio.to_thread(
            lambda: list(api.list_models(
                search=task,
                sort=sort,
                limit=limit * 3,
            ))
        )

        candidates = []
        for m in models:
            license_tag = ""
            tags = list(m.tags or [])
            for t in tags:
                if t in ALLOWED_LICENSES:
                    license_tag = t
                    break

            # Estimate size from safetensors info if available
            size_gb = 0.0
            if hasattr(m, "safetensors") and m.safetensors:
                total_bytes = sum(
                    v.get("total", 0) if isinstance(v, dict) else 0
                    for v in (m.safetensors.get("parameters", {}) or {}).values()
                ) * 2  # fp16 ≈ 2 bytes per param
                size_gb = total_bytes / (1024**3)

            if size_gb > max_size_gb and size_gb > 0:
                continue
            if (m.downloads or 0) < min_downloads:
                continue

            candidates.append(ModelCandidate(
                model_id=m.id,
                task=task,
                downloads=m.downloads or 0,
                likes=m.likes or 0,
                license=license_tag,
                tags=tags[:10],
                size_estimate_gb=round(size_gb, 2),
            ))

            if len(candidates) >= limit:
                break

        logger.info("Found %d model candidates for task=%s", len(candidates), task)
        return candidates

    async def _search_via_http(
        self, task: str, *, max_size_gb: float, min_downloads: int,
        sort: str, limit: int,
    ) -> list[ModelCandidate]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://huggingface.co/api/models",
                params={"search": task, "sort": sort, "direction": "-1", "limit": limit},
            )
            resp.raise_for_status()
            models = resp.json()

        candidates = []
        for m in models:
            if (m.get("downloads", 0) or 0) < min_downloads:
                continue
            tags = m.get("tags", [])
            license_tag = next((t for t in tags if t in ALLOWED_LICENSES), "")
            candidates.append(ModelCandidate(
                model_id=m["id"],
                task=task,
                downloads=m.get("downloads", 0),
                likes=m.get("likes", 0),
                license=license_tag,
                tags=tags[:10],
            ))
        return candidates[:limit]

    async def search_papers(self, topic: str, *, limit: int = 10) -> list[PaperResult]:
        """Search arXiv-linked papers on HuggingFace."""
        try:
            return await self._search_papers_hf(topic, limit=limit)
        except ImportError:
            return await self._search_papers_http(topic, limit=limit)

    async def _search_papers_hf(self, topic: str, *, limit: int) -> list[PaperResult]:
        from huggingface_hub import HfApi
        api = HfApi(token=self.hf_token)
        papers = await asyncio.to_thread(api.list_papers, query=topic)

        results = []
        for p in papers:
            results.append(PaperResult(
                paper_id=p.id,
                title=p.title,
                authors=[a.name for a in (p.authors or [])],
                summary=p.summary[:500] if p.summary else "",
            ))
            if len(results) >= limit:
                break
        logger.info("Found %d papers for topic=%s", len(results), topic)
        return results

    async def _search_papers_http(self, topic: str, *, limit: int) -> list[PaperResult]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://huggingface.co/api/daily_papers",
                params={"search": topic, "limit": limit},
            )
            if resp.status_code != 200:
                return []
            papers = resp.json()

        return [
            PaperResult(
                paper_id=p.get("paper", {}).get("id", ""),
                title=p.get("paper", {}).get("title", ""),
                summary=p.get("paper", {}).get("summary", "")[:500],
            )
            for p in papers[:limit]
        ]

    async def recommend(
        self, task: str, *, max_size_gb: float = 4.0, top_k: int = 5,
    ) -> dict:
        """Full research: find models + related papers, return ranked report."""
        models = await self.search_base_models(task, max_size_gb=max_size_gb)
        papers = await self.search_papers(f"{task} fine-tuning")

        ranked = sorted(models, key=lambda m: (m.downloads * 0.7 + m.likes * 0.3), reverse=True)
        top = ranked[:top_k]

        return {
            "task": task,
            "max_size_gb": max_size_gb,
            "candidates": [
                {
                    "model_id": m.model_id,
                    "downloads": m.downloads,
                    "likes": m.likes,
                    "license": m.license,
                    "size_gb": m.size_estimate_gb,
                    "tags": m.tags,
                }
                for m in top
            ],
            "papers": [
                {"id": p.paper_id, "title": p.title}
                for p in papers[:5]
            ],
        }
